from __future__ import annotations

import hashlib
import html
import json
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts


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


def _text(value: Any, limit: int = 20_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


class Build223AIAndSourceConsolidationService:
    """Canonical Phase-8 facade for AI, retrieval, source routing and reliability.

    Build 223 deliberately does not replace the proven implementation services in
    Builds 215-222. It makes them internal components behind one stable API, one
    case configuration and one trace chain. Legacy services stay available only for
    compatibility and regression safety.
    """

    BUILD = "223.0"
    COMPONENTS = {
        "ai_provider": {
            "canonical_service": "build215",
            "legacy_services": ["local_ai_agent_101", "build207"],
            "responsibility": "local model discovery, local-only execution and model policy",
        },
        "conversation_retrieval": {
            "canonical_service": "build216",
            "legacy_services": ["build206", "case_ai_retrieval_2"],
            "responsibility": "persistent conversation, source-grounded retrieval and training examples",
        },
        "planning_routing": {
            "canonical_service": "build217",
            "legacy_services": ["guided_source_routing", "research_strategy_128"],
            "responsibility": "investigation planning and deterministic source routing",
        },
        "source_execution": {
            "canonical_service": "build223",
            "legacy_services": ["build218", "build220"],
            "responsibility": "single governed entry point for all productive source adapters",
        },
        "source_reliability": {
            "canonical_service": "build219",
            "legacy_services": ["source_reliability_98", "reliability_quality_125"],
            "responsibility": "health, drift, cooldown, circuit breaker and quarantine",
        },
        "research_loop": {
            "canonical_service": "build221",
            "legacy_services": ["build207", "controlled_ai_agents"],
            "responsibility": "human-governed planner, verifier, critic, translator and reporter loop",
        },
        "qualification": {
            "canonical_service": "build222",
            "legacy_services": [],
            "responsibility": "Phase-7 qualification baseline retained for comparative measurement",
        },
    }

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        local_ai: Any,
        conversation: Any,
        planner: Any,
        source_pack1: Any,
        reliability: Any,
        source_pack2: Any,
        research_loop: Any,
        qualification: Any,
        workspace: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.local_ai, self.conversation, self.planner = local_ai, conversation, planner
        self.source_pack1, self.reliability, self.source_pack2 = source_pack1, reliability, source_pack2
        self.research_loop, self.qualification, self.workspace = research_loop, qualification, workspace
        self.actor = actor
        self.seed_component_map()

    # ---------- canonical configuration ----------
    def seed_component_map(self) -> dict[str, Any]:
        now = now_ts()
        for key, definition in self.COMPONENTS.items():
            payload = {"component_key": key, **definition, "status": "active", "updated_at": now}
            self.db.execute(
                """INSERT INTO canonical_component_map_223(component_key,canonical_service,legacy_services_json,responsibility,status,created_at,updated_at,payload_sha256)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(component_key) DO UPDATE SET canonical_service=excluded.canonical_service,legacy_services_json=excluded.legacy_services_json,responsibility=excluded.responsibility,status=excluded.status,updated_at=excluded.updated_at,payload_sha256=excluded.payload_sha256""",
                (key, definition["canonical_service"], dumps(definition["legacy_services"]), definition["responsibility"], "active", now, now, _hash(payload)),
            )
        return {"build": self.BUILD, "components": len(self.COMPONENTS), "canonical_facade": "build223"}

    def ensure_case_config(self, *, case_id: str, actor: str | None = None) -> dict[str, Any]:
        self._case(case_id)
        row = self.db.one("SELECT * FROM consolidation_case_config_223 WHERE case_id=?", (case_id,))
        if row:
            return self._public_config(row)
        now, who = now_ts(), actor or self.actor
        payload = {
            "case_id": case_id, "config_version": 1, "working_language": "de",
            "max_retrieval_chunks": 12, "max_source_actions": 5, "live_sources_enabled": False,
            "canonical_ai_service": "build223", "canonical_retrieval_service": "build216",
            "canonical_source_service": "build223", "canonical_reliability_service": "build219",
            "created_by": who, "created_at": now, "updated_by": who, "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO consolidation_case_config_223 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (case_id, 1, "de", 12, 5, 0, "build223", "build216", "build223", "build219", who, now, who, now, _hash(payload)),
        )
        self._event(case_id, "consolidation_config_created", "case", case_id, {"config_version": 1}, who)
        return payload

    def update_case_config(
        self,
        *,
        case_id: str,
        working_language: str,
        max_retrieval_chunks: int,
        max_source_actions: int,
        live_sources_enabled: bool,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"KONSOLIDIERUNG 223 {case_id} KONFIGURIEREN":
            raise PermissionError("explicit approval required")
        current = self.ensure_case_config(case_id=case_id, actor=actor)
        now = now_ts()
        payload = {
            **current,
            "config_version": int(current["config_version"]) + 1,
            "working_language": _text(working_language, 20).strip() or "de",
            "max_retrieval_chunks": max(1, min(int(max_retrieval_chunks), 30)),
            "max_source_actions": max(1, min(int(max_source_actions), 10)),
            "live_sources_enabled": bool(live_sources_enabled),
            "updated_by": actor,
            "updated_at": now,
        }
        self.db.execute(
            """UPDATE consolidation_case_config_223 SET config_version=?,working_language=?,max_retrieval_chunks=?,max_source_actions=?,live_sources_enabled=?,updated_by=?,updated_at=?,payload_sha256=? WHERE case_id=?""",
            (payload["config_version"], payload["working_language"], payload["max_retrieval_chunks"], payload["max_source_actions"], int(payload["live_sources_enabled"]), actor, now, _hash(payload), case_id),
        )
        self._event(case_id, "consolidation_config_updated", "case", case_id, {"config_version": payload["config_version"], "live_sources_enabled": payload["live_sources_enabled"]}, actor)
        return payload

    # ---------- one canonical entry point ----------
    def send_message(self, *, session_id: str, message: str, message_language: str, actor: str, confirmation: str) -> dict[str, Any]:
        session = self.conversation._session(session_id)
        if confirmation != f"AI INVESTIGATOR 223 {session_id} SENDEN":
            raise PermissionError("explicit approval required")
        trace = self._start_trace(session["case_id"], "conversation.send", "conversation_retrieval", {"session_id": session_id, "message_language": message_language}, actor)
        try:
            conversational_v2 = getattr(self, "_conversation_v2", None)
            if conversational_v2 is not None:
                result = conversational_v2.send_turn(
                    session_id=session_id, message=message, message_language=message_language, actor=actor,
                    confirmation=f"CONVERSATIONAL TURN 227 {session_id} SENDEN",
                )
            else:
                result = self.conversation.send_message(session_id=session_id, message=message, message_language=message_language, actor=actor, confirmation=f"CHAT 216 {session_id} SENDEN")
            self._finish_trace(trace, "completed", result, {"grounding": float(result.get("source_grounding_score") or 0), "citation_count": len(result.get("evidence_refs") or [])})
            return {**result, "trace_id": trace, "canonical_service": "build223"}
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise

    def create_plan(self, *, session_id: str, objective: str, question_language: str, actor: str, confirmation: str) -> dict[str, Any]:
        session = self.conversation._session(session_id)
        if confirmation != f"INVESTIGATION PLAN 223 {session_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        trace = self._start_trace(session["case_id"], "planning.create", "planning_routing", {"session_id": session_id, "question_language": question_language}, actor)
        try:
            result = self.planner.create_plan(session_id=session_id, objective=objective, question_language=question_language, actor=actor, confirmation=f"INVESTIGATION PLAN 217 {session_id} ERSTELLEN")
            source_intelligence = None
            optimizer = getattr(self, "_source_intelligence_v1", None)
            if optimizer is not None:
                source_intelligence = optimizer.optimize_plan(plan_id=result["plan_id"], actor=actor)
            self._finish_trace(trace, "completed", result, {"route_count": len(result.get("source_recommendations") or []), "source_intelligence": bool(source_intelligence)})
            return {**result, "trace_id": trace, "canonical_service": "build223", "source_intelligence": source_intelligence}
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise

    def run_source(
        self,
        *,
        case_id: str,
        adapter_key: str,
        target_type: str,
        target_value: str,
        purpose: str,
        actor: str,
        confirmation: str,
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if confirmation != f"SOURCE 223 {case_id} {adapter_key} AUSFUEHREN":
            raise PermissionError("explicit approval required")
        config = self.ensure_case_config(case_id=case_id, actor=actor)
        trace = self._start_trace(case_id, "source.execute", "source_execution", {"adapter_key": adapter_key, "target_type": target_type, "live_sources_enabled": config["live_sources_enabled"]}, actor)
        try:
            pack1_keys = {row["adapter_key"] for row in self.source_pack1.catalog()}
            pack2_keys = {row["adapter_key"] for row in self.source_pack2.catalog()}
            if adapter_key in pack1_keys:
                if not config["live_sources_enabled"] and adapter_key.endswith("_public"):
                    result = {"build": self.BUILD, "adapter_key": adapter_key, "status": "blocked", "result_count": 0, "reason": "live sources disabled in canonical case configuration"}
                else:
                    result = self.reliability.run_adapter(case_id=case_id, adapter_key=adapter_key, target_type=target_type, target_value=target_value, purpose=purpose, actor=actor, confirmation=f"RELIABLE SOURCE 219 {case_id} {adapter_key} AUSFUEHREN")
            elif adapter_key in pack2_keys:
                if not config["live_sources_enabled"] and adapter_key in {"wayback_public", "gleif_public"}:
                    result = {"build": self.BUILD, "adapter_key": adapter_key, "status": "blocked", "result_count": 0, "reason": "live sources disabled in canonical case configuration"}
                else:
                    result = self.source_pack2.run_adapter(case_id=case_id, adapter_key=adapter_key, target_type=target_type, target_value=target_value, purpose=purpose, actor=actor, options=options or {}, confirmation=f"SOURCE PACK 220 {case_id} {adapter_key} AUSFUEHREN")
            else:
                raise KeyError(f"unknown canonical adapter: {adapter_key}")
            status = "blocked" if result.get("status") == "blocked" else "completed"
            self._finish_trace(trace, status, result, {"result_count": int(result.get("result_count") or 0), "adapter_key": adapter_key})
            return {**result, "trace_id": trace, "canonical_service": "build223"}
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise

    def create_research_loop(self, *, case_id: str, session_id: str, objective: str, working_language: str, max_cycles: int, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"AI RESEARCH LOOP 223 {case_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        trace = self._start_trace(case_id, "research_loop.create", "research_loop", {"session_id": session_id, "max_cycles": max_cycles}, created_by)
        try:
            result = self.research_loop.create_loop(case_id=case_id, session_id=session_id, objective=objective, working_language=working_language, max_cycles=max_cycles, created_by=created_by, confirmation=f"AI RESEARCH LOOP 221 {case_id} ANLEGEN")
            self._finish_trace(trace, "completed", result, {"max_cycles": result.get("max_cycles", max_cycles)})
            return {**result, "trace_id": trace, "canonical_service": "build223"}
        except Exception as exc:
            self._fail_trace(trace, exc)
            raise

    # ---------- baseline and status ----------
    def create_baseline(self, *, case_id: str, created_by: str, confirmation: str) -> dict[str, Any]:
        if confirmation != f"PHASE8 BASELINE 223 {case_id} ERSTELLEN":
            raise PermissionError("explicit approval required")
        self.ensure_case_config(case_id=case_id, actor=created_by)
        chat = self.conversation.dashboard(case_id=case_id)
        pack1 = self.source_pack1.dashboard(case_id=case_id)
        reliable = self.reliability.dashboard(case_id=case_id)
        pack2 = self.source_pack2.dashboard(case_id=case_id)
        loop = self.research_loop.dashboard(case_id)
        baseline_id, now = new_id("baseline223"), now_ts()
        ai_metrics = {
            "sessions": len(chat.get("sessions") or []),
            "messages": len(chat.get("messages") or []),
            "benchmarks": len(chat.get("benchmarks") or []),
            "research_loops": len(loop.get("loops") or []),
            "research_findings": len(loop.get("findings") or []),
        }
        source_metrics = {
            "pack1_adapters": len(pack1.get("adapters") or []),
            "pack2_adapters": len(pack2.get("adapters") or []),
            "pack1_runs": len(pack1.get("runs") or []),
            "pack2_runs": len(pack2.get("runs") or []),
            "reliability_profiles": len(reliable.get("profiles") or []),
        }
        retrieval_metrics = {
            "indexed_source_types": len(chat.get("chunks") or []),
            "indexed_chunks": sum(int(row.get("n") or 0) for row in chat.get("chunks") or []),
            "training_groups": len(chat.get("training") or []),
        }
        service_map = {key: value["canonical_service"] for key, value in self.COMPONENTS.items()}
        payload = {"baseline_id": baseline_id, "case_id": case_id, "baseline_version": 1, "ai_metrics": ai_metrics, "source_metrics": source_metrics, "retrieval_metrics": retrieval_metrics, "service_map": service_map, "created_by": created_by, "created_at": now}
        self.db.execute(
            "INSERT INTO consolidation_baselines_223 VALUES(?,?,?,?,?,?,?,?,?,?)",
            (baseline_id, case_id, 1, dumps(ai_metrics), dumps(source_metrics), dumps(retrieval_metrics), dumps(service_map), created_by, now, _hash(payload)),
        )
        self._event(case_id, "phase8_baseline_created", "consolidation_baseline", baseline_id, {"ai_metrics": ai_metrics, "source_metrics": source_metrics}, created_by)
        return payload

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        config = self.ensure_case_config(case_id=case_id)
        return {
            "build": self.BUILD,
            "config": config,
            "components": self.db.all("SELECT * FROM canonical_component_map_223 ORDER BY component_key"),
            "traces": self.db.all("SELECT * FROM investigation_traces_223 WHERE case_id=? ORDER BY started_at DESC LIMIT 50", (case_id,)),
            "baselines": self.db.all("SELECT * FROM consolidation_baselines_223 WHERE case_id=? ORDER BY created_at DESC LIMIT 10", (case_id,)),
            "sessions": self.db.all("SELECT session_id,title,status,updated_at FROM ai_chat_sessions_216 WHERE case_id=? ORDER BY updated_at DESC LIMIT 20", (case_id,)),
            "loops": self.db.all("SELECT loop_id,status,current_role,current_cycle,updated_at FROM ai_research_loops_221 WHERE case_id=? ORDER BY updated_at DESC LIMIT 20", (case_id,)),
            "source_catalog": self._source_catalog(),
            "policy": {
                "single_canonical_facade": True,
                "legacy_services_compatibility_only": True,
                "human_review": True,
                "source_grounded": True,
                "automatic_identity_confirmation": False,
                "automatic_external_action": False,
            },
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        config = data["config"]
        sources = "".join(
            f"<tr><td>{esc(row['adapter_key'])}</td><td>{esc(row['title'])}</td><td>{esc(row['pack'])}</td><td>{esc(row.get('state',''))}</td><td>{esc(row.get('network_capable',False))}</td></tr>"
            for row in data["source_catalog"]
        ) or "<tr><td colspan='5'>Kein Quellenadapter registriert.</td></tr>"
        traces = "".join(
            f"<tr><td>{esc(row['operation'])}</td><td>{esc(row['component'])}</td><td>{esc(row['status'])}</td><td>{esc(row['trace_id'])}</td><td>{esc(row['started_at'])}</td></tr>"
            for row in data["traces"][:20]
        ) or "<tr><td colspan='5'>Noch keine Build-223-Traces.</td></tr>"
        components = "".join(
            f"<tr><td>{esc(row['component_key'])}</td><td>{esc(row['canonical_service'])}</td><td>{esc(row['responsibility'])}</td><td>{esc(row['status'])}</td></tr>"
            for row in data["components"]
        )
        return f"""
<section class='card' id='build223_consolidation'>
<h2>Fallarbeitsraum 223 · AI & Quellen konsolidiert</h2>
<p>Ein kanonischer Einstieg für Chat, Planung, Quellen, Reliability und den governeden Research Loop. Bestehende Build-215–222-Dienste bleiben interne, getestete Komponenten.</p>
<div class='grid'>
<div class='card'><h3>Kanonische Fallkonfiguration</h3><form method='post' action='/build223/config'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><label>Arbeitssprache</label><input name='working_language' value='{esc(config['working_language'])}'><label>Retrieval-Chunks</label><input name='max_retrieval_chunks' type='number' min='1' max='30' value='{esc(config['max_retrieval_chunks'])}'><label>Quellenaktionen pro Zyklus</label><input name='max_source_actions' type='number' min='1' max='10' value='{esc(config['max_source_actions'])}'><label class='inline'><input type='checkbox' name='live_sources_enabled' value='1' {'checked' if config['live_sources_enabled'] else ''}> Kontrollierte Live-Quellen erlauben</label><button>Konfiguration speichern</button></form></div>
<div class='card'><h3>Phase-8-Ausgangsmessung</h3><p>Erfasst AI-, Retrieval-, Quellen- und Reliability-Stand für spätere Vergleiche.</p><form method='post' action='/build223/baseline'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><button>Baseline erstellen</button></form><p><b>{len(data['baselines'])}</b> Baselines · <b>{len(data['traces'])}</b> Traces</p></div>
</div>
<div class='grid'>
<div class='card'><h3>Kanonischer AI-Chat</h3><form method='post' action='/build223/chat'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216-Session-ID' required><input name='message_language' value='{esc(config['working_language'])}'><textarea name='message' rows='5' placeholder='Fallbezogene Ermittlungsfrage' required></textarea><button>Mit AI-Ermittler arbeiten</button></form></div>
<div class='card'><h3>Kanonischer Ermittlungsplan</h3><form method='post' action='/build223/plan'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216-Session-ID' required><input name='question_language' value='{esc(config['working_language'])}'><textarea name='objective' rows='5' placeholder='Ermittlungsziel' required></textarea><button>Plan erzeugen</button></form></div>
<div class='card'><h3>Kanonischer Quellenlauf</h3><form method='post' action='/build223/source-run'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='adapter_key' placeholder='Adapter-Key' required><input name='target_type' placeholder='username, name, public_url ...' required><input name='target_value' placeholder='Suchwert' required><textarea name='purpose' rows='3' placeholder='Konkreter Fallzweck' required></textarea><button>Reliability-geschützt ausführen</button></form></div>
<div class='card'><h3>Governed Research Loop</h3><form method='post' action='/build223/loop-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216-Session-ID' required><input name='working_language' value='{esc(config['working_language'])}'><input name='max_cycles' type='number' min='1' max='5' value='3'><textarea name='objective' rows='4' placeholder='Ziel des Research Loops' required></textarea><button>Loop anlegen</button></form></div>
</div>
<h3>Kanonische Komponenten</h3><div class='table-wrap'><table><thead><tr><th>Bereich</th><th>Kanonischer Dienst</th><th>Verantwortung</th><th>Status</th></tr></thead><tbody>{components}</tbody></table></div>
<h3>Produktive Quellen</h3><div class='table-wrap'><table><thead><tr><th>Adapter</th><th>Titel</th><th>Paket</th><th>Reliability</th><th>Netzwerk</th></tr></thead><tbody>{sources}</tbody></table></div>
<h3>End-to-End-Traces</h3><div class='table-wrap'><table><thead><tr><th>Operation</th><th>Komponente</th><th>Status</th><th>Trace-ID</th><th>Start</th></tr></thead><tbody>{traces}</tbody></table></div>
</section>
"""

    # ---------- trace helpers ----------
    def _start_trace(self, case_id: str, operation: str, component: str, inputs: Mapping[str, Any], actor: str, parent_trace_id: str = "") -> str:
        self._case(case_id)
        trace_id, now = new_id("trace223"), now_ts()
        safe_input = {k: v for k, v in dict(inputs).items() if k not in {"target_value", "message", "prompt", "token", "authorization", "password"}}
        payload = {"trace_id": trace_id, "case_id": case_id, "parent_trace_id": parent_trace_id, "operation": operation, "component": component, "status": "running", "started_by": actor, "started_at": now, "input_sha256": _hash(inputs)}
        self.db.execute(
            "INSERT INTO investigation_traces_223 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (trace_id, case_id, parent_trace_id, operation, component, "running", actor, now, "", _hash(inputs), "", dumps({"safe_input": safe_input}), "", "", _hash(payload)),
        )
        return trace_id

    def _finish_trace(self, trace_id: str, status: str, output: Mapping[str, Any], metrics: Mapping[str, Any]) -> None:
        row = self.db.one("SELECT * FROM investigation_traces_223 WHERE trace_id=?", (trace_id,))
        if not row:
            raise KeyError(trace_id)
        finished = now_ts()
        payload = {"trace_id": trace_id, "status": status, "finished_at": finished, "output_sha256": _hash(output), "metrics": dict(metrics)}
        self.db.execute("UPDATE investigation_traces_223 SET status=?,finished_at=?,output_sha256=?,metrics_json=?,payload_sha256=? WHERE trace_id=?", (status, finished, _hash(output), dumps(metrics), _hash(payload), trace_id))
        self._event(row["case_id"], "canonical_trace_finished", "investigation_trace", trace_id, {"operation": row["operation"], "status": status, "metrics": dict(metrics)}, row["started_by"])

    def _fail_trace(self, trace_id: str, exc: Exception) -> None:
        row = self.db.one("SELECT * FROM investigation_traces_223 WHERE trace_id=?", (trace_id,))
        if not row:
            return
        finished = now_ts()
        payload = {"trace_id": trace_id, "status": "failed", "finished_at": finished, "error_class": type(exc).__name__, "error_message": _text(exc, 1000)}
        self.db.execute("UPDATE investigation_traces_223 SET status='failed',finished_at=?,error_class=?,error_message=?,payload_sha256=? WHERE trace_id=?", (finished, type(exc).__name__, _text(exc, 1000), _hash(payload), trace_id))
        self._event(row["case_id"], "canonical_trace_failed", "investigation_trace", trace_id, {"operation": row["operation"], "error_class": type(exc).__name__}, row["started_by"])

    def _source_catalog(self) -> list[dict[str, Any]]:
        profiles = {row["adapter_key"]: row for row in self.db.all("SELECT * FROM source_reliability_profiles_219")}
        rows: list[dict[str, Any]] = []
        for item in self.source_pack1.catalog():
            profile = profiles.get(item["adapter_key"], {})
            rows.append({"adapter_key": item["adapter_key"], "title": item["title"], "pack": "digital_identity", "network_capable": bool(item.get("network_capable")), "state": profile.get("state", "unknown")})
        for item in self.source_pack2.catalog():
            profile = profiles.get(item["adapter_key"], {})
            rows.append({"adapter_key": item["adapter_key"], "title": item["title"], "pack": "web_archive_org_document", "network_capable": bool(item.get("network_capable")), "state": profile.get("state", "unknown")})
        return sorted(rows, key=lambda x: (x["pack"], x["adapter_key"]))

    def _public_config(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {**dict(row), "live_sources_enabled": bool(row["live_sources_enabled"])}

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError(case_id)

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> str:
        prev = self.db.one("SELECT event_hash FROM build223_events WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,))
        previous = prev["event_hash"] if prev else "0" * 64
        event_id, now = new_id("evt223"), now_ts()
        safe = {k: v for k, v in dict(payload).items() if k not in {"target_value", "message", "token", "authorization", "raw", "prompt", "response"}}
        body = {"event_id": event_id, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "actor": actor, "payload": safe, "previous_hash": previous, "created_at": now}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build223_events VALUES(?,?,?,?,?,?,?,?,?,?)", (event_id, case_id, event_type, object_type, object_id, actor, dumps(safe), previous, event_hash, now))
        if self.audit is not None and hasattr(self.audit, "log"):
            self.audit.log(event_type, object_type, object_id, case_id, safe)
        return event_id
