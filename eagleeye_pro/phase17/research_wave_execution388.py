from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Mapping

BUILD = "388.0"
POLICY_ID = "phase17.governed-research-wave-execution.v388"
CONFIRM_START = "START WAVES"
CONFIRM_ATTACH = "ATTACH DISPATCH"
CONFIRM_ADVANCE = "ADVANCE WAVE"
TERMINAL_JOB_STATES = frozenset({"succeeded", "failed", "cancelled", "dead_letter"})
NONTERMINAL_JOB_STATES = frozenset({"queued", "running", "retry_wait"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha(value: Any) -> str:
    raw = value if isinstance(value, (bytes, bytearray)) else _canon(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _j(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if isinstance(value, str) else (value if value is not None else default)
    except Exception:
        return default


@dataclass(frozen=True, slots=True)
class WaveJobObservation388:
    phase17_source_id: str
    canonical_source_id: str
    dispatch_id: str
    job_id: str
    crawl_run_id: str
    search_run_id: str
    job_status: str
    coverage_state: str
    object_ids: tuple[str, ...]
    pages_fetched: int
    pages_stored: int
    errors: int
    evidence_ref: str


class GovernedResearchWave388:
    """Observe and govern sequential Phase-17 research waves.

    This controller never issues GO grants, never supplies LIVE confirmation, never claims
    worker leases and never performs network I/O. It binds Build-387 dispatch receipts to
    Build-384 wave plans, observes terminal Phase-15 worker results, records evidence-linked
    coverage observations, and returns a fail-closed continuation decision before another
    wave may be advanced explicitly by an investigator.
    """

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        runtime384: Any,
        executor387: Any,
        operations365: Any,
        opsec380: Any,
        governance: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db = db
        self.audit = audit
        self.runtime384 = runtime384
        self.executor387 = executor387
        self.operations365 = operations365
        self.opsec380 = opsec380
        self.governance = governance
        self.actor = actor
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS research_wave_session_388 (
                session_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                wave_plan_id TEXT NOT NULL,
                acquisition_packet_id TEXT NOT NULL,
                wave_plan_hash TEXT NOT NULL,
                packet_hash TEXT NOT NULL,
                current_wave INTEGER NOT NULL,
                max_wave INTEGER NOT NULL,
                state TEXT NOT NULL,
                decision TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                UNIQUE(case_id, wave_plan_id, acquisition_packet_id),
                FOREIGN KEY(acquisition_packet_id) REFERENCES acquisition_packet_385(packet_id)
            );
            CREATE TABLE IF NOT EXISTS research_wave_binding_388 (
                session_id TEXT NOT NULL,
                wave_number INTEGER NOT NULL,
                source_ids_json TEXT NOT NULL,
                dispatch_ids_json TEXT NOT NULL,
                state TEXT NOT NULL,
                result_json TEXT NOT NULL,
                decision TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                PRIMARY KEY(session_id, wave_number),
                FOREIGN KEY(session_id) REFERENCES research_wave_session_388(session_id)
            );
            CREATE TABLE IF NOT EXISTS research_wave_result_388 (
                result_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                wave_number INTEGER NOT NULL,
                phase17_source_id TEXT NOT NULL,
                canonical_source_id TEXT NOT NULL,
                dispatch_id TEXT NOT NULL,
                job_id TEXT NOT NULL UNIQUE,
                crawl_run_id TEXT NOT NULL,
                search_run_id TEXT NOT NULL,
                job_status TEXT NOT NULL,
                coverage_state TEXT NOT NULL,
                object_ids_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                coverage_observation_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES research_wave_session_388(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_wave_session_388_case ON research_wave_session_388(case_id, updated_at);
            CREATE INDEX IF NOT EXISTS idx_wave_result_388_session ON research_wave_result_388(session_id, wave_number, observed_at);
            """
        )
        self.db.conn.commit()

    def _authorize(self, identity: Mapping[str, Any], case_id: str, capability: str, object_type: str, object_id: str) -> None:
        self.governance.authorize(dict(identity), case_id=case_id, capability=capability, object_type=object_type, object_id=object_id)

    def _session_row(self, case_id: str, session_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_wave_session_388 WHERE session_id=? AND case_id=?", (session_id, case_id))
        if not row:
            raise KeyError(session_id)
        return row

    def _binding_row(self, session_id: str, wave_number: int) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_wave_binding_388 WHERE session_id=? AND wave_number=?", (session_id, int(wave_number)))
        if not row:
            raise KeyError(f"wave {wave_number}")
        return row

    def _rehash_session(self, row: Mapping[str, Any]) -> str:
        body = {k: row[k] for k in row if k != "record_hash"}
        return _sha(body)

    def _rehash_binding(self, row: Mapping[str, Any]) -> str:
        body = {k: row[k] for k in row if k != "record_hash"}
        return _sha(body)

    def _validate_session_bindings(self, session: Mapping[str, Any]) -> None:
        packet = self.db.one("SELECT packet_hash,wave_plan_id FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?", (session["acquisition_packet_id"], session["case_id"]))
        plan = self.db.one("SELECT plan_hash FROM research_wave_plan_384 WHERE wave_plan_id=? AND case_id=?", (session["wave_plan_id"], session["case_id"]))
        if not packet or not plan:
            raise PermissionError("wave session predecessor record missing")
        if str(packet.get("packet_hash") or "") != str(session.get("packet_hash") or ""):
            raise PermissionError("acquisition packet hash changed after wave-session start")
        if str(packet.get("wave_plan_id") or "") != str(session.get("wave_plan_id") or ""):
            raise PermissionError("acquisition packet wave-plan binding changed")
        if str(plan.get("plan_hash") or "") != str(session.get("wave_plan_hash") or ""):
            raise PermissionError("research wave plan hash changed after session start")

    def start_session(
        self,
        *,
        case_id: str,
        wave_plan_id: str,
        packet_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_START:
            raise PermissionError(f"explicit confirmation {CONFIRM_START} required")
        self._authorize(identity, case_id, "crawler.run", "phase17_wave_session_v388", wave_plan_id)
        plan = self.db.one("SELECT * FROM research_wave_plan_384 WHERE wave_plan_id=? AND case_id=?", (wave_plan_id, case_id))
        packet = self.db.one("SELECT * FROM acquisition_packet_385 WHERE packet_id=? AND case_id=?", (packet_id, case_id))
        if not plan or not packet:
            raise KeyError(wave_plan_id if not plan else packet_id)
        if str(packet.get("wave_plan_id") or "") != wave_plan_id:
            raise ValueError("acquisition packet is not bound to wave plan")
        packet_body = dict(_j(packet.get("packet_json"), {}) or {})
        by_wave: dict[int, list[str]] = {}
        for item in packet_body.get("items") or []:
            number = int(item.get("wave_number") or 0)
            source_id = str(item.get("source_id") or "")
            if number > 0 and source_id:
                by_wave.setdefault(number, []).append(source_id)
        if not by_wave:
            raise ValueError("acquisition packet contains no research-wave items")
        min_wave, max_wave = min(by_wave), max(by_wave)
        actor = str(identity.get("username") or self.actor)[:120]
        created = _now()
        session_id = "wave388_" + secrets.token_hex(12)
        record = {
            "session_id": session_id,
            "case_id": case_id,
            "wave_plan_id": wave_plan_id,
            "acquisition_packet_id": packet_id,
            "wave_plan_hash": str(plan.get("plan_hash") or ""),
            "packet_hash": str(packet.get("packet_hash") or ""),
            "current_wave": min_wave,
            "max_wave": max_wave,
            "state": "active",
            "decision": "awaiting_go",
            "created_by": actor,
            "created_at": created,
            "updated_at": created,
        }
        with self.db.transaction(immediate=True):
            self.db.execute(
                "INSERT INTO research_wave_session_388(session_id,case_id,wave_plan_id,acquisition_packet_id,wave_plan_hash,packet_hash,current_wave,max_wave,state,decision,created_by,created_at,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*record.values(), _sha(record)),
            )
            for number in sorted(by_wave):
                b = {
                    "session_id": session_id,
                    "wave_number": number,
                    "source_ids_json": _canon(sorted(set(by_wave[number]))),
                    "dispatch_ids_json": "[]",
                    "state": "awaiting_go" if number == min_wave else "planned",
                    "result_json": "{}",
                    "decision": "awaiting_go" if number == min_wave else "not_current",
                    "updated_at": created,
                }
                self.db.execute(
                    "INSERT INTO research_wave_binding_388(session_id,wave_number,source_ids_json,dispatch_ids_json,state,result_json,decision,updated_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?)",
                    (*b.values(), _sha(b)),
                )
        self.audit.log("PHASE17_388_WAVE_SESSION_STARTED", "research_wave_session", session_id, case_id=case_id, details={
            "wave_plan_id": wave_plan_id, "packet_id": packet_id, "waves": sorted(by_wave),
            "automatic_go_issuance": False, "automatic_live_confirmation": False, "policy": POLICY_ID,
        })
        return self.session(case_id=case_id, session_id=session_id)

    def attach_dispatch(
        self,
        *,
        case_id: str,
        session_id: str,
        dispatch_id: str,
        identity: Mapping[str, Any],
        confirmation: str,
    ) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_ATTACH:
            raise PermissionError(f"explicit confirmation {CONFIRM_ATTACH} required")
        self._authorize(identity, case_id, "crawler.run", "phase17_wave_dispatch_v388", dispatch_id)
        with self.db.transaction(immediate=True):
            session = self._session_row(case_id, session_id)
            self._validate_session_bindings(session)
            if str(session.get("state")) != "active":
                raise PermissionError("wave session is not active")
            wave_number = int(session["current_wave"])
            binding = self._binding_row(session_id, wave_number)
            dispatch = self.executor387.dispatch(case_id=case_id, dispatch_id=dispatch_id)
            if str(dispatch.get("acquisition_packet_id") or "") != str(session["acquisition_packet_id"]):
                raise PermissionError("dispatch belongs to a different acquisition packet")
            allowed_sources = set(_j(binding.get("source_ids_json"), []) or [])
            dispatch_sources = {str(i.get("phase17_source_id") or "") for i in dispatch.get("items") or []}
            if not dispatch_sources or not dispatch_sources.issubset(allowed_sources):
                raise PermissionError("dispatch source scope is outside current wave")
            dispatches = list(_j(binding.get("dispatch_ids_json"), []) or [])
            if dispatch_id not in dispatches:
                dispatches.append(dispatch_id)
            updated = _now()
            new_binding = dict(binding)
            new_binding.update({"dispatch_ids_json": _canon(dispatches), "state": "in_progress", "decision": "awaiting_worker_results", "updated_at": updated})
            new_binding["record_hash"] = self._rehash_binding(new_binding)
            self.db.execute(
                "UPDATE research_wave_binding_388 SET dispatch_ids_json=?,state=?,decision=?,updated_at=?,record_hash=? WHERE session_id=? AND wave_number=?",
                (new_binding["dispatch_ids_json"], new_binding["state"], new_binding["decision"], updated, new_binding["record_hash"], session_id, wave_number),
            )
            new_session = dict(session)
            new_session.update({"decision": "awaiting_worker_results", "updated_at": updated})
            new_session["record_hash"] = self._rehash_session(new_session)
            self.db.execute("UPDATE research_wave_session_388 SET decision=?,updated_at=?,record_hash=? WHERE session_id=?", (new_session["decision"], updated, new_session["record_hash"], session_id))
        self.audit.log("PHASE17_388_DISPATCH_ATTACHED", "research_wave_session", session_id, case_id=case_id, details={"dispatch_id": dispatch_id, "wave_number": wave_number, "policy": POLICY_ID})
        return self.session(case_id=case_id, session_id=session_id)

    def _boundary_status(self, case_id: str) -> dict[str, Any]:
        readiness = dict(self.operations365.readiness(case_id=case_id))
        breaker = bool(self.operations365.circuit_breaker_required(case_id=case_id))
        opsec = dict(self.opsec380.status())
        unsafe = any(bool(opsec.get(k)) for k in ("system_mutations", "firewall_mutation", "credential_mutation", "automatic_release_authority"))
        return {
            "operations_ready": bool(readiness.get("local_operational_ready")) and not breaker,
            "operations_blockers": list(readiness.get("blockers") or []),
            "circuit_breaker_required": breaker,
            "opsec_safe": not unsafe,
            "opsec_unsafe_mutation": unsafe,
        }

    def _observe_item(self, *, case_id: str, dispatch_id: str, item: Mapping[str, Any]) -> WaveJobObservation388:
        job_id = str(item.get("job_id") or "")
        job = self.db.one("SELECT * FROM phase15_jobs WHERE job_id=? AND case_id=?", (job_id, case_id))
        if not job:
            raise RuntimeError(f"dispatched job missing: {job_id}")
        status = str(job.get("status") or "")
        crawl_run_id = str(item.get("crawl_run_id") or "")
        search_run_id = str(item.get("search_run_id") or job.get("search_run_id") or "")
        crawl = self.db.one("SELECT * FROM phase15_crawl_runs WHERE crawl_run_id=? AND case_id=?", (crawl_run_id, case_id)) if crawl_run_id else None
        result = dict(_j(job.get("result_json"), {}) or {})
        pages_fetched = int((crawl or {}).get("pages_fetched") or result.get("pages_fetched") or 0)
        pages_stored = int((crawl or {}).get("pages_stored") or result.get("pages_stored") or 0)
        summary = dict(_j((crawl or {}).get("summary_json"), {}) or {})
        errors = int(summary.get("errors") or result.get("errors") or 0)
        objects = self.db.all(
            "SELECT object_id FROM phase15_objects WHERE case_id=? AND search_run_id=? AND source_id=? ORDER BY created_at,object_id",
            (case_id, search_run_id, str(item.get("canonical_source_id") or "")),
        ) if search_run_id else []
        object_ids = tuple(str(r["object_id"]) for r in objects)
        if status == "succeeded":
            if pages_stored > 0 or object_ids:
                coverage = "partial" if errors > 0 else "succeeded"
            else:
                coverage = "no_result_observed"
        elif status in {"failed", "dead_letter"}:
            coverage = "failed"
        elif status == "cancelled":
            coverage = "blocked"
        else:
            coverage = "pending"
        evidence_ref = f"phase15_job:{job_id};crawl:{crawl_run_id or '-'};objects:{len(object_ids)}"
        return WaveJobObservation388(
            phase17_source_id=str(item.get("phase17_source_id") or ""),
            canonical_source_id=str(item.get("canonical_source_id") or ""),
            dispatch_id=dispatch_id,
            job_id=job_id,
            crawl_run_id=crawl_run_id,
            search_run_id=search_run_id,
            job_status=status,
            coverage_state=coverage,
            object_ids=object_ids,
            pages_fetched=pages_fetched,
            pages_stored=pages_stored,
            errors=errors,
            evidence_ref=evidence_ref,
        )

    def _persist_terminal_observation(self, *, session_id: str, wave_number: int, observation: WaveJobObservation388) -> str:
        existing = self.db.one("SELECT result_id FROM research_wave_result_388 WHERE job_id=?", (observation.job_id,))
        if existing:
            return str(existing["result_id"])
        observed_at = _now()
        coverage_id = self.runtime384.repository.record_coverage(
            case_id=self._session_row_by_id(session_id)["case_id"],
            source_id=observation.phase17_source_id,
            state=observation.coverage_state,
            evidence_ref=observation.evidence_ref,
            detail=f"Build 388 terminal worker observation: {observation.job_status}",
            observed_at=observed_at,
        )
        body = asdict(observation) | {"coverage_observation_id": coverage_id, "observed_at": observed_at}
        result_id = "wres388_" + _sha({"session_id": session_id, "wave": wave_number, "job_id": observation.job_id})[:24]
        record = {
            "result_id": result_id,
            "session_id": session_id,
            "wave_number": wave_number,
            "phase17_source_id": observation.phase17_source_id,
            "canonical_source_id": observation.canonical_source_id,
            "dispatch_id": observation.dispatch_id,
            "job_id": observation.job_id,
            "crawl_run_id": observation.crawl_run_id,
            "search_run_id": observation.search_run_id,
            "job_status": observation.job_status,
            "coverage_state": observation.coverage_state,
            "object_ids_json": _canon(observation.object_ids),
            "result_json": _canon(body),
            "coverage_observation_id": coverage_id,
            "observed_at": observed_at,
        }
        self.db.execute(
            "INSERT INTO research_wave_result_388(result_id,session_id,wave_number,phase17_source_id,canonical_source_id,dispatch_id,job_id,crawl_run_id,search_run_id,job_status,coverage_state,object_ids_json,result_json,coverage_observation_id,observed_at,record_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (*record.values(), _sha(record)),
        )
        return result_id

    def _session_row_by_id(self, session_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM research_wave_session_388 WHERE session_id=?", (session_id,))
        if not row:
            raise KeyError(session_id)
        return row

    def reconcile(self, *, case_id: str, session_id: str, identity: Mapping[str, Any]) -> dict[str, Any]:
        self._authorize(identity, case_id, "case.read", "phase17_wave_reconcile_v388", session_id)
        with self.db.transaction(immediate=True):
            session = self._session_row(case_id, session_id)
            self._validate_session_bindings(session)
            wave_number = int(session["current_wave"])
            binding = self._binding_row(session_id, wave_number)
            dispatch_ids = list(_j(binding.get("dispatch_ids_json"), []) or [])
            observations: list[WaveJobObservation388] = []
            for dispatch_id in dispatch_ids:
                dispatch = self.executor387.dispatch(case_id=case_id, dispatch_id=str(dispatch_id))
                if str(dispatch.get("acquisition_packet_id") or "") != str(session["acquisition_packet_id"]):
                    raise PermissionError("attached dispatch packet changed")
                for item in dispatch.get("items") or []:
                    observations.append(self._observe_item(case_id=case_id, dispatch_id=str(dispatch_id), item=item))

            nonterminal = [o for o in observations if o.job_status not in TERMINAL_JOB_STATES]
            terminal = [o for o in observations if o.job_status in TERMINAL_JOB_STATES]
            for obs in terminal:
                self._persist_terminal_observation(session_id=session_id, wave_number=wave_number, observation=obs)

            boundary = {"operations_ready": True, "operations_blockers": [], "circuit_breaker_required": False, "opsec_safe": True, "opsec_unsafe_mutation": False, "deferred_until_terminal": True}
            if dispatch_ids and not nonterminal:
                boundary = self._boundary_status(case_id) | {"deferred_until_terminal": False}
            planned_sources = set(_j(binding.get("source_ids_json"), []) or [])
            prepared_sources = {str(r.get("source_id") or "") for r in self.db.all(
                "SELECT source_id FROM acquisition_preparation_385 WHERE case_id=? AND packet_id=? AND canonical_source_id IS NOT NULL AND canonical_source_id<>''",
                (case_id, session["acquisition_packet_id"]),
            )}
            executable_planned_sources = planned_sources & prepared_sources
            dispatched_sources = {o.phase17_source_id for o in observations}
            undispatched = sorted(executable_planned_sources - dispatched_sources)
            coverage_states = [o.coverage_state for o in terminal]
            if not dispatch_ids:
                state, decision = "awaiting_go", "awaiting_go"
            elif nonterminal:
                state, decision = "in_progress", "awaiting_worker_results"
            elif any(s in {"failed", "blocked"} for s in coverage_states):
                state, decision = "review_required", "human_review_required"
            elif any(s == "no_result_observed" for s in coverage_states):
                state, decision = "review_required", "no_result_review"
            elif undispatched:
                state, decision = "review_required", "undispatched_sources_review"
            elif not boundary["operations_ready"]:
                state, decision = "paused", "pause_operations"
            elif not boundary["opsec_safe"]:
                state, decision = "paused", "pause_opsec"
            elif wave_number < int(session["max_wave"]):
                state, decision = "complete", "ready_for_next_wave_go"
            else:
                state, decision = "complete", "session_complete"

            requested_classes = []
            for row in self.db.all("SELECT objective_json FROM coverage_objective_384 WHERE wave_plan_id=? ORDER BY ordinal", (session["wave_plan_id"],)):
                objective = dict(_j(row.get("objective_json"), {}) or {})
                cls = str(objective.get("source_class") or "")
                if cls:
                    requested_classes.append(cls)
            coverage = self.runtime384.repository.coverage_report(case_id, requested_source_classes=requested_classes)
            result = {
                "build": BUILD,
                "policy": POLICY_ID,
                "session_id": session_id,
                "case_id": case_id,
                "wave_number": wave_number,
                "wave_state": state,
                "decision": decision,
                "dispatch_ids": dispatch_ids,
                "observations": [asdict(o) for o in observations],
                "terminal_jobs": len(terminal),
                "nonterminal_jobs": len(nonterminal),
                "undispatched_sources": undispatched,
                "boundary": boundary,
                "coverage": {
                    "successful_or_partial_count": coverage.successful_or_partial_count,
                    "observed_source_count": coverage.observed_source_count,
                    "gaps": [asdict(g) for g in coverage.gaps],
                    "no_result_is_nonexistence": coverage.no_result_is_nonexistence,
                },
                "automatic_go_issuance": False,
                "automatic_live_confirmation": False,
                "automatic_worker_claim": False,
                "automatic_evidence_promotion": False,
            }
            updated = _now()
            nb = dict(binding)
            nb.update({"state": state, "decision": decision, "result_json": _canon(result), "updated_at": updated})
            nb["record_hash"] = self._rehash_binding(nb)
            self.db.execute("UPDATE research_wave_binding_388 SET state=?,result_json=?,decision=?,updated_at=?,record_hash=? WHERE session_id=? AND wave_number=?", (state, nb["result_json"], decision, updated, nb["record_hash"], session_id, wave_number))
            ns = dict(session)
            final_state = "completed" if decision == "session_complete" else ("review_required" if state == "review_required" else "active")
            ns.update({"state": final_state, "decision": decision, "updated_at": updated})
            ns["record_hash"] = self._rehash_session(ns)
            self.db.execute("UPDATE research_wave_session_388 SET state=?,decision=?,updated_at=?,record_hash=? WHERE session_id=?", (final_state, decision, updated, ns["record_hash"], session_id))

        self.audit.log("PHASE17_388_WAVE_RECONCILED", "research_wave_session", session_id, case_id=case_id, details={
            "wave_number": wave_number, "decision": decision, "terminal_jobs": len(terminal), "nonterminal_jobs": len(nonterminal),
            "automatic_go_issuance": False, "automatic_evidence_promotion": False, "policy": POLICY_ID,
        })
        return result

    def advance(self, *, case_id: str, session_id: str, identity: Mapping[str, Any], confirmation: str) -> dict[str, Any]:
        if str(confirmation or "").strip().upper() != CONFIRM_ADVANCE:
            raise PermissionError(f"explicit confirmation {CONFIRM_ADVANCE} required")
        self._authorize(identity, case_id, "crawler.run", "phase17_wave_advance_v388", session_id)
        with self.db.transaction(immediate=True):
            session = self._session_row(case_id, session_id)
            self._validate_session_bindings(session)
            if str(session.get("decision") or "") != "ready_for_next_wave_go":
                raise PermissionError("current wave is not ready for explicit advance")
            current = int(session["current_wave"])
            nxt = current + 1
            if nxt > int(session["max_wave"]):
                raise PermissionError("no next research wave")
            if not self.db.one("SELECT 1 x FROM research_wave_binding_388 WHERE session_id=? AND wave_number=?", (session_id, nxt)):
                raise PermissionError("next research wave is not represented in packet")
            updated = _now()
            cur_binding = self._binding_row(session_id, current)
            cb = dict(cur_binding); cb.update({'state':'complete','decision':'advanced','updated_at':updated}); cb['record_hash'] = self._rehash_binding(cb)
            self.db.execute("UPDATE research_wave_binding_388 SET state='complete',decision='advanced',updated_at=?,record_hash=? WHERE session_id=? AND wave_number=?", (updated, cb['record_hash'], session_id, current))
            next_binding = self._binding_row(session_id, nxt)
            nb = dict(next_binding); nb.update({"state":"awaiting_go","decision":"awaiting_go","updated_at":updated}); nb["record_hash"] = self._rehash_binding(nb)
            self.db.execute("UPDATE research_wave_binding_388 SET state=?,decision=?,updated_at=?,record_hash=? WHERE session_id=? AND wave_number=?", (nb["state"],nb["decision"],updated,nb["record_hash"],session_id,nxt))
            ns = dict(session); ns.update({"current_wave":nxt,"state":"active","decision":"awaiting_go","updated_at":updated}); ns["record_hash"] = self._rehash_session(ns)
            self.db.execute("UPDATE research_wave_session_388 SET current_wave=?,state=?,decision=?,updated_at=?,record_hash=? WHERE session_id=?", (nxt,"active","awaiting_go",updated,ns["record_hash"],session_id))
        self.audit.log("PHASE17_388_WAVE_ADVANCED", "research_wave_session", session_id, case_id=case_id, details={"from_wave": current, "to_wave": nxt, "automatic_go_issuance": False, "policy": POLICY_ID})
        return self.session(case_id=case_id, session_id=session_id)

    def session(self, *, case_id: str, session_id: str) -> dict[str, Any]:
        session = self._session_row(case_id, session_id)
        bindings = self.db.all("SELECT * FROM research_wave_binding_388 WHERE session_id=? ORDER BY wave_number", (session_id,))
        results = self.db.all("SELECT * FROM research_wave_result_388 WHERE session_id=? ORDER BY wave_number,observed_at,result_id", (session_id,))
        return {
            **{k: session[k] for k in session if k != "record_hash"},
            "record_hash": session["record_hash"],
            "waves": [
                {
                    "wave_number": int(b["wave_number"]),
                    "source_ids": list(_j(b["source_ids_json"], []) or []),
                    "dispatch_ids": list(_j(b["dispatch_ids_json"], []) or []),
                    "state": b["state"],
                    "decision": b["decision"],
                    "result": dict(_j(b["result_json"], {}) or {}),
                } for b in bindings
            ],
            "result_count": len(results),
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "automatic_worker_claim": False,
            "automatic_evidence_promotion": False,
        }

    def verify_session(self, *, case_id: str, session_id: str) -> dict[str, Any]:
        session = self._session_row(case_id, session_id)
        session_valid = secrets.compare_digest(str(session.get("record_hash") or ""), self._rehash_session(session))
        bindings = self.db.all("SELECT * FROM research_wave_binding_388 WHERE session_id=?", (session_id,))
        binding_valid = all(secrets.compare_digest(str(b.get("record_hash") or ""), self._rehash_binding(b)) for b in bindings)
        results = self.db.all("SELECT * FROM research_wave_result_388 WHERE session_id=?", (session_id,))
        result_valid = all(secrets.compare_digest(str(r.get("record_hash") or ""), _sha({k:r[k] for k in r if k != "record_hash"})) for r in results)
        return {"session_id": session_id, "session_hash_valid": session_valid, "binding_hashes_valid": binding_valid, "result_hashes_valid": result_valid, "valid": session_valid and binding_valid and result_valid}

    def status(self) -> dict[str, Any]:
        sessions = int((self.db.one("SELECT COUNT(*) n FROM research_wave_session_388") or {}).get("n") or 0)
        results = int((self.db.one("SELECT COUNT(*) n FROM research_wave_result_388") or {}).get("n") or 0)
        return {
            "build": BUILD,
            "policy": POLICY_ID,
            "sessions": sessions,
            "terminal_results_observed": results,
            "sequential_wave_governance": True,
            "coverage_feedback": True,
            "artifact_provenance_feedback": True,
            "automatic_go_issuance": False,
            "automatic_live_confirmation": False,
            "automatic_worker_claim": False,
            "direct_network_fetch": False,
            "automatic_evidence_promotion": False,
            "automatic_scope_expansion": False,
        }
