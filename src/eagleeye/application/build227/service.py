from __future__ import annotations

import hashlib
import html
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping, Sequence

from eagleeye_pro.core.database import dumps, new_id, now_ts

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_URL_RE = re.compile(r"https?://[^\s]+", re.I)
_CORRECTION_RE = re.compile(
    r"(?i)(du hast (?:vorhin|zuvor)|korrigiere|berichtige|widerspruch|noch einmal neu|"
    r"ignoriere meine bisherige annahme|prüfe .* neu|previous answer|correct your|reconsider)"
)
_PROMPT_INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all|previous) instructions|system prompt|developer message|execute (?:this|the) tool|"
    r"do not cite|forget the evidence|ignoriere .*anweisung|überspringe .*anweisung|führe .*befehl aus)"
)


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


def _text(value: Any, limit: int = 200_000) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def _clamp(value: Any) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except Exception:
        return 0.0


class Build227ConversationalInvestigator2Service:
    """Persistent, claim-aware conversational investigator for Phase 8.

    Build 227 keeps the proven Build 216 model boundary and Build 225/226 source
    intelligence, but adds explicit investigation threads, hypotheses, visible
    context snapshots, corrections, resumable turn state, cooperative stop/retry
    and validated progressive response chunks. The model still has no shell,
    browser, database or source-execution capability.
    """

    BUILD = "227.0"
    MAX_TURNS = 200

    def __init__(
        self,
        db: Any,
        audit: Any,
        *,
        conversation: Any,
        retrieval: Any,
        source_intelligence: Any,
        consolidation: Any,
        workspace: Any,
        actor: str = "local-analyst",
    ) -> None:
        self.db, self.audit = db, audit
        self.conversation, self.retrieval = conversation, retrieval
        self.source_intelligence, self.consolidation = source_intelligence, consolidation
        self.workspace, self.actor = workspace, actor
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="eagleeye-build227")
        self._futures: dict[str, Any] = {}
        self._future_lock = threading.RLock()
        # Canonical Build 223 delegates conversation turns to this service.
        self.consolidation._conversation_v2 = self

    # ---------- lifecycle and state ----------
    def ensure_state(
        self,
        *,
        session_id: str,
        investigation_goal: str = "",
        working_language: str = "",
        actor: str | None = None,
    ) -> dict[str, Any]:
        session = self.conversation._session(session_id)
        row = self.db.one("SELECT * FROM conversational_states_227 WHERE session_id=?", (session_id,))
        if row:
            return row
        now, who = now_ts(), actor or self.actor
        goal = _text(investigation_goal, 4000).strip() or _text(session.get("title"), 4000).strip()
        language = _text(working_language, 20).strip() or _text(session.get("working_language"), 20).strip() or "de"
        payload = {
            "session_id": session_id, "case_id": session["case_id"], "investigation_goal": goal,
            "working_language": language, "status": "active", "turn_count": 0,
            "conversation_summary": "", "active_thread_id": "", "last_context_snapshot_id": "",
            "last_turn_id": "", "created_by": who, "created_at": now, "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO conversational_states_227 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (session_id, session["case_id"], goal, language, "active", 0, "", "", "", "", who, now, now, _hash(payload)),
        )
        default_thread = self._create_thread_internal(
            session_id=session_id, case_id=session["case_id"], title="Hauptermittlungsstrang",
            objective=goal or "Fallbezogene PersonenOSINT-Prüfung", priority=100, actor=who,
        )
        self.db.execute(
            "UPDATE conversational_states_227 SET active_thread_id=?,updated_at=? WHERE session_id=?",
            (default_thread["thread_id"], now_ts(), session_id),
        )
        self._event(session["case_id"], "conversation_state_created", "chat_session", session_id, {"working_language": language}, who)
        return self.db.one("SELECT * FROM conversational_states_227 WHERE session_id=?", (session_id,)) or payload

    def configure_state(
        self,
        *,
        session_id: str,
        investigation_goal: str,
        working_language: str,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"CONVERSATIONAL INVESTIGATOR 227 {session_id} KONFIGURIEREN":
            raise PermissionError("explicit approval required")
        state = self.ensure_state(session_id=session_id, actor=actor)
        goal = _text(investigation_goal, 4000).strip() or state["investigation_goal"]
        language = _text(working_language, 20).strip() or state["working_language"]
        now = now_ts()
        payload = {**state, "investigation_goal": goal, "working_language": language, "updated_at": now}
        self.db.execute(
            "UPDATE conversational_states_227 SET investigation_goal=?,working_language=?,updated_at=?,payload_sha256=? WHERE session_id=?",
            (goal, language, now, _hash(payload), session_id),
        )
        self._event(state["case_id"], "conversation_state_configured", "chat_session", session_id, {"working_language": language}, actor)
        return self.db.one("SELECT * FROM conversational_states_227 WHERE session_id=?", (session_id,)) or payload

    # ---------- investigation threads and hypotheses ----------
    def create_thread(
        self,
        *,
        session_id: str,
        title: str,
        objective: str,
        priority: int,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"INVESTIGATION THREAD 227 {session_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        state = self.ensure_state(session_id=session_id, actor=actor)
        result = self._create_thread_internal(
            session_id=session_id, case_id=state["case_id"], title=title,
            objective=objective, priority=max(0, min(int(priority), 100)), actor=actor,
        )
        if not state.get("active_thread_id"):
            self.db.execute("UPDATE conversational_states_227 SET active_thread_id=?,updated_at=? WHERE session_id=?", (result["thread_id"], now_ts(), session_id))
        return result

    def set_thread_status(
        self,
        *,
        thread_id: str,
        status: str,
        resolution_note: str,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        row = self._thread(thread_id)
        if confirmation != f"INVESTIGATION THREAD 227 {thread_id} AKTUALISIEREN":
            raise PermissionError("explicit approval required")
        if status not in {"active", "deferred", "resolved", "abandoned"}:
            raise ValueError("invalid thread status")
        now = now_ts()
        payload = {**row, "status": status, "resolution_note": _text(resolution_note, 5000), "updated_at": now}
        self.db.execute(
            "UPDATE investigation_threads_227 SET status=?,resolution_note=?,updated_at=?,payload_sha256=? WHERE thread_id=?",
            (status, payload["resolution_note"], now, _hash(payload), thread_id),
        )
        if status == "active":
            self.db.execute("UPDATE conversational_states_227 SET active_thread_id=?,updated_at=? WHERE session_id=?", (thread_id, now, row["session_id"]))
        self._event(row["case_id"], "investigation_thread_updated", "thread", thread_id, {"status": status}, actor)
        return self._thread(thread_id)

    def add_hypothesis(
        self,
        *,
        session_id: str,
        thread_id: str,
        hypothesis_text: str,
        confidence: float,
        supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str],
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        if confirmation != f"HYPOTHESIS 227 {session_id} ANLEGEN":
            raise PermissionError("explicit approval required")
        state = self.ensure_state(session_id=session_id, actor=actor)
        return self._insert_hypothesis(
            session_id=session_id, case_id=state["case_id"], thread_id=thread_id or state.get("active_thread_id", ""),
            text=hypothesis_text, confidence=confidence, supporting_refs=supporting_refs,
            contradicting_refs=contradicting_refs, status="active", origin="investigator", actor=actor,
        )

    def revise_hypothesis(
        self,
        *,
        hypothesis_id: str,
        revised_text: str,
        status: str,
        confidence: float,
        supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str],
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        old = self._hypothesis(hypothesis_id)
        if confirmation != f"HYPOTHESIS 227 {hypothesis_id} REVIDIEREN":
            raise PermissionError("explicit approval required")
        if status not in {"active", "supported", "challenged", "rejected", "unresolved"}:
            raise ValueError("invalid hypothesis status")
        now = now_ts()
        self.db.execute("UPDATE investigation_hypotheses_227 SET status='superseded',updated_at=? WHERE hypothesis_id=?", (now, hypothesis_id))
        result = self._insert_hypothesis(
            session_id=old["session_id"], case_id=old["case_id"], thread_id=old["thread_id"],
            text=revised_text, confidence=confidence, supporting_refs=supporting_refs,
            contradicting_refs=contradicting_refs, status=status, origin="investigator_revision", actor=actor,
            supersedes=hypothesis_id,
        )
        self._event(old["case_id"], "hypothesis_revised", "hypothesis", result["hypothesis_id"], {"supersedes": hypothesis_id, "status": status}, actor)
        return result

    # ---------- conversation turn execution ----------
    def send_turn(
        self,
        *,
        session_id: str,
        message: str,
        message_language: str,
        actor: str,
        confirmation: str,
        retry_of_turn_id: str = "",
        correction_target_turn_id: str = "",
    ) -> dict[str, Any]:
        if confirmation != f"CONVERSATIONAL TURN 227 {session_id} SENDEN":
            raise PermissionError("explicit approval required")
        turn = self._queue_turn(
            session_id=session_id, message=message, message_language=message_language,
            actor=actor, retry_of_turn_id=retry_of_turn_id,
            correction_target_turn_id=correction_target_turn_id,
        )
        return self._execute_turn(turn["turn_id"], actor=actor)

    def start_turn(
        self,
        *,
        session_id: str,
        message: str,
        message_language: str,
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        """Start a persistent local background turn and return immediately.

        This is used by the browser UI for status polling and cooperative stop.
        The synchronous ``send_turn`` remains available for deterministic scripts.
        """
        if confirmation != f"CONVERSATIONAL TURN 227 {session_id} STARTEN":
            raise PermissionError("explicit approval required")
        turn = self._queue_turn(session_id=session_id, message=message, message_language=message_language, actor=actor)
        with self._future_lock:
            self._futures[turn["turn_id"]] = self._executor.submit(self._execute_turn, turn["turn_id"], actor)
        return {**turn, "background": True, "pollable": True, "stop_is_cooperative": True}

    def request_stop(self, *, turn_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        turn = self._turn(turn_id)
        if confirmation != f"CONVERSATIONAL TURN 227 {turn_id} STOPPEN":
            raise PermissionError("explicit approval required")
        if turn["status"] in {"completed", "failed", "stopped", "superseded"}:
            return {**turn, "stop_requested": bool(turn["stop_requested"]), "already_terminal": True}
        self.db.execute("UPDATE conversational_turns_227 SET stop_requested=1,updated_at=? WHERE turn_id=?", (now_ts(), turn_id))
        self._append_chunk(turn_id, "status", "Stop angefordert. Ein laufender lokaler Modellaufruf wird kooperativ beendet; bereits empfangene, noch nicht validierte Ausgabe wird nicht als Befund übernommen.")
        self._event(turn["case_id"], "conversation_turn_stop_requested", "turn", turn_id, {}, actor)
        return self._turn(turn_id)

    def retry_turn(self, *, turn_id: str, actor: str, confirmation: str) -> dict[str, Any]:
        old = self._turn(turn_id)
        if confirmation != f"CONVERSATIONAL TURN 227 {turn_id} WIEDERHOLEN":
            raise PermissionError("explicit approval required")
        if old["status"] not in {"failed", "stopped", "completed"}:
            raise ValueError("only terminal turns can be retried")
        return self.send_turn(
            session_id=old["session_id"], message=old["user_message"], message_language=old["message_language"],
            actor=actor, confirmation=f"CONVERSATIONAL TURN 227 {old['session_id']} SENDEN", retry_of_turn_id=turn_id,
        )

    def record_correction(
        self,
        *,
        target_turn_id: str,
        correction_text: str,
        evidence_refs: Sequence[str],
        actor: str,
        confirmation: str,
    ) -> dict[str, Any]:
        turn = self._turn(target_turn_id)
        if confirmation != f"CONVERSATION CORRECTION 227 {target_turn_id} SPEICHERN":
            raise PermissionError("explicit approval required")
        text = _text(correction_text, 10_000).strip()
        if not text:
            raise ValueError("correction text required")
        refs = self.workspace._valid_refs(turn["case_id"], list(evidence_refs))
        if list(evidence_refs) and refs != list(evidence_refs):
            raise ValueError("correction contains invalid case evidence references")
        cid, now = new_id("correction227"), now_ts()
        payload = {
            "correction_id": cid, "session_id": turn["session_id"], "case_id": turn["case_id"],
            "target_turn_id": target_turn_id, "corrected_turn_id": "", "correction_text": text,
            "evidence_refs": refs, "status": "reviewed", "created_by": actor, "created_at": now,
        }
        self.db.execute(
            "INSERT INTO conversational_corrections_227 VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (cid, turn["session_id"], turn["case_id"], target_turn_id, "", text, dumps(refs), "reviewed", actor, now, _hash(payload)),
        )
        self._event(turn["case_id"], "conversation_correction_recorded", "turn", target_turn_id, {"correction_id": cid, "evidence_refs": refs}, actor)
        return payload

    # ---------- inspection and UI ----------
    def turn_status(self, *, turn_id: str) -> dict[str, Any]:
        turn = self._turn(turn_id)
        chunks = self.db.all("SELECT * FROM conversational_stream_chunks_227 WHERE turn_id=? ORDER BY sequence_no", (turn_id,))
        snapshot = self.db.one("SELECT * FROM conversational_context_snapshots_227 WHERE turn_id=? ORDER BY created_at DESC LIMIT 1", (turn_id,))
        return {**turn, "response": _loads(turn.get("response_json"), {}), "citations": _loads(turn.get("citations_json"), []), "chunks": chunks, "context_snapshot": self._public_snapshot(snapshot) if snapshot else None}

    def dashboard(self, *, case_id: str) -> dict[str, Any]:
        self._case(case_id)
        return {
            "build": self.BUILD,
            "states": self.db.all("SELECT * FROM conversational_states_227 WHERE case_id=? ORDER BY updated_at DESC LIMIT 30", (case_id,)),
            "threads": self.db.all("SELECT * FROM investigation_threads_227 WHERE case_id=? ORDER BY priority DESC,updated_at DESC LIMIT 100", (case_id,)),
            "hypotheses": self.db.all("SELECT * FROM investigation_hypotheses_227 WHERE case_id=? ORDER BY updated_at DESC LIMIT 100", (case_id,)),
            "turns": self.db.all("SELECT * FROM conversational_turns_227 WHERE case_id=? ORDER BY created_at DESC LIMIT 80", (case_id,)),
            "corrections": self.db.all("SELECT * FROM conversational_corrections_227 WHERE case_id=? ORDER BY created_at DESC LIMIT 50", (case_id,)),
            "policy": {
                "source_grounded": True, "claim_aware": True, "human_controlled": True,
                "automatic_source_execution": False, "validated_stream_chunks": True,
                "cooperative_stop": True, "resumable_after_restart": True,
            },
        }

    def render_workspace_panel(self, *, case_id: str, csrf: str) -> str:
        data = self.dashboard(case_id=case_id)
        esc = lambda x: html.escape(str(x if x is not None else ""), quote=True)
        states = "".join(
            f"<tr><td><code>{esc(x['session_id'])}</code></td><td>{esc(x['investigation_goal'])}</td><td>{esc(x['turn_count'])}</td><td>{esc(x['status'])}</td><td>{esc(x['updated_at'])}</td></tr>"
            for x in data["states"]
        ) or "<tr><td colspan='5'>Noch kein Build-227-Fallgespräch.</td></tr>"
        threads = "".join(
            f"<tr><td><code>{esc(x['thread_id'])}</code></td><td>{esc(x['title'])}</td><td>{esc(x['status'])}</td><td>{esc(x['priority'])}</td><td>{esc(x['objective'])}</td></tr>"
            for x in data["threads"]
        ) or "<tr><td colspan='5'>Noch keine Ermittlungsstränge.</td></tr>"
        hypotheses = "".join(
            f"<tr><td><code>{esc(x['hypothesis_id'])}</code></td><td>{esc(x['hypothesis_text'])}</td><td>{esc(x['status'])}</td><td>{esc(round(float(x['confidence']),2))}</td></tr>"
            for x in data["hypotheses"]
        ) or "<tr><td colspan='4'>Noch keine Hypothesen.</td></tr>"
        turns = "".join(
            f"<tr><td><code>{esc(x['turn_id'])}</code></td><td>{esc(x['sequence_no'])}</td><td>{esc(x['user_message'][:220])}</td><td>{esc(x['status'])}</td><td>{esc(x['retrieval_run_id'])}</td></tr>"
            for x in data["turns"]
        ) or "<tr><td colspan='5'>Noch keine Build-227-Turns.</td></tr>"
        return f"""
<section class='card' id='build227_conversational_investigator'><h2>Conversational Investigator 2.0 · Build 227</h2>
<p>Längerer, claim-zentrierter Ermittlungsdialog mit aktiven Strängen, Hypothesen, sichtbaren Kontext-Snapshots, Selbstkorrektur, validiertem Chunk-Streaming, Stop/Retry und Neustartwiederaufnahme.</p>
<div class='grid two'>
<div><h3>Fallgespräch konfigurieren</h3><form method='post' action='/build227/configure'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Build-216-Session-ID' required><input name='working_language' value='de'><textarea name='investigation_goal' rows='4' placeholder='Übergeordnetes Ermittlungsziel' required></textarea><button>Dialogzustand anlegen oder aktualisieren</button></form>
<h3>Neuer Ermittlungsstrang</h3><form method='post' action='/build227/thread-create'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Session-ID' required><input name='title' placeholder='Titel' required><textarea name='objective' rows='3' placeholder='Ziel des Strangs' required></textarea><input name='priority' type='number' min='0' max='100' value='50'><button>Strang anlegen</button></form></div>
<div><h3>Ermittlungs-Turn starten</h3><form method='post' action='/build227/turn-start'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='session_id' placeholder='Session-ID' required><input name='message_language' value='de'><textarea name='message' rows='6' placeholder='Frage, Gegenhypothese oder Korrektur' required></textarea><button>Turn starten</button></form>
<h3>Turn steuern</h3><form method='post' action='/build227/turn-stop'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='turn_id' placeholder='Turn-ID' required><button class='danger'>Kooperativ stoppen</button></form><form method='post' action='/build227/turn-retry'><input type='hidden' name='csrf' value='{esc(csrf)}'><input type='hidden' name='case_id' value='{esc(case_id)}'><input name='turn_id' placeholder='Turn-ID' required><button class='ghost'>Turn wiederholen</button></form></div>
</div>
<div class='table-wrap'><table><thead><tr><th>Session</th><th>Ziel</th><th>Turns</th><th>Status</th><th>Aktualisiert</th></tr></thead><tbody>{states}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Strang</th><th>Titel</th><th>Status</th><th>Priorität</th><th>Ziel</th></tr></thead><tbody>{threads}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Hypothese</th><th>Text</th><th>Status</th><th>Konfidenz</th></tr></thead><tbody>{hypotheses}</tbody></table></div>
<div class='table-wrap'><table><thead><tr><th>Turn</th><th>Nr.</th><th>Frage</th><th>Status</th><th>Retrieval</th></tr></thead><tbody>{turns}</tbody></table></div>
</section>"""

    # ---------- internals ----------
    def _queue_turn(
        self,
        *,
        session_id: str,
        message: str,
        message_language: str,
        actor: str,
        retry_of_turn_id: str = "",
        correction_target_turn_id: str = "",
    ) -> dict[str, Any]:
        state = self.ensure_state(session_id=session_id, actor=actor)
        if state["status"] != "active":
            raise ValueError("conversation state is not active")
        question = _text(message, 20_000).strip()
        if not question:
            raise ValueError("message required")
        sanitized = _PROMPT_INJECTION_RE.sub("[UNTRUSTED_INSTRUCTION_REMOVED]", question)
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT COALESCE(MAX(sequence_no),0) AS n FROM conversational_turns_227 WHERE session_id=?", (session_id,)) or {"n": 0}
            sequence = int(row["n"]) + 1
            if sequence > self.MAX_TURNS:
                raise ValueError("conversation turn limit reached")
            tid, now = new_id("turn227"), now_ts()
            payload = {
                "turn_id": tid, "session_id": session_id, "case_id": state["case_id"], "sequence_no": sequence,
                "user_message": sanitized, "message_language": _text(message_language, 20) or state["working_language"],
                "status": "queued", "retry_of_turn_id": retry_of_turn_id, "correction_target_turn_id": correction_target_turn_id,
                "created_by": actor, "created_at": now, "updated_at": now,
            }
            self.db.execute(
                "INSERT INTO conversational_turns_227 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, session_id, state["case_id"], sequence, sanitized, payload["message_language"], "queued", retry_of_turn_id,
                 correction_target_turn_id, "", "", "", "", "{}", "[]", "", 0, actor, "", "", now, now, _hash(payload)),
            )
        self._append_chunk(tid, "status", "Turn wurde persistent angelegt.")
        self._event(state["case_id"], "conversation_turn_queued", "turn", tid, {"sequence_no": sequence, "retry_of": retry_of_turn_id}, actor)
        return self._turn(tid)

    def _execute_turn(self, turn_id: str, actor: str) -> dict[str, Any]:
        turn = self._turn(turn_id)
        if turn["status"] not in {"queued", "failed"}:
            return self.turn_status(turn_id=turn_id)
        now = now_ts()
        self.db.execute("UPDATE conversational_turns_227 SET status='running',started_at=?,updated_at=?,error_text='' WHERE turn_id=?", (now, now, turn_id))
        self._append_chunk(turn_id, "status", "Fallkontext und Quellenstrategie werden vorbereitet.")
        try:
            if self._stop_requested(turn_id):
                return self._mark_stopped(turn_id, actor, "vor dem Modellaufruf")
            state = self.ensure_state(session_id=turn["session_id"], actor=actor)
            threads = self._active_threads(turn["session_id"])
            hypotheses = self._active_hypotheses(turn["session_id"])
            source_strategy = self._source_strategy(turn, state, actor)
            prompt = self._compose_prompt(turn, state, threads, hypotheses, source_strategy)
            self._append_chunk(turn_id, "status", "Claim-zentriertes Retrieval und lokaler AI-Aufruf laufen.")
            result = self.conversation.send_message(
                session_id=turn["session_id"], message=prompt, message_language=turn["message_language"], actor=actor,
                confirmation=f"CHAT 216 {turn['session_id']} SENDEN",
            )
            if self._stop_requested(turn_id):
                return self._mark_stopped(turn_id, actor, "nach dem Modellaufruf vor Übernahme in den Build-227-Fallstand", result=result)
            answer = dict(result.get("answer") or {})
            citations = list(result.get("citations") or result.get("evidence_refs") or [])
            retrieval = dict(result.get("retrieval") or {})
            self._sync_ai_hypotheses(turn, answer, actor)
            summary = self._roll_summary(state.get("conversation_summary", ""), turn["user_message"], answer)
            snapshot = self._save_snapshot(
                turn=turn, summary=summary, threads=self._active_threads(turn["session_id"]),
                hypotheses=self._active_hypotheses(turn["session_id"]), retrieval=retrieval,
                source_strategy=source_strategy,
            )
            completed = now_ts()
            response = {
                "answer": answer, "citations": citations, "retrieval": retrieval,
                "source_strategy": source_strategy, "context_snapshot_id": snapshot["snapshot_id"],
                "correction_requested": bool(_CORRECTION_RE.search(turn["user_message"])),
                "human_review_required": True, "automatic_source_execution": False,
            }
            self.db.execute(
                """UPDATE conversational_turns_227 SET status='completed',base_user_message_id=?,base_assistant_message_id=?,
                retrieval_run_id=?,source_query_id=?,response_json=?,citations_json=?,completed_at=?,updated_at=?,payload_sha256=? WHERE turn_id=?""",
                (result.get("user_message_id", ""), result.get("assistant_message_id", ""), retrieval.get("retrieval_run_id", ""),
                 source_strategy.get("query_id", ""), dumps(response), dumps(citations), completed, completed, _hash(response), turn_id),
            )
            current_state = self.ensure_state(session_id=turn["session_id"], actor=actor)
            self.db.execute(
                """UPDATE conversational_states_227 SET turn_count=turn_count+1,conversation_summary=?,last_context_snapshot_id=?,
                last_turn_id=?,updated_at=?,payload_sha256=? WHERE session_id=?""",
                (summary, snapshot["snapshot_id"], turn_id, completed, _hash({**current_state, "conversation_summary": summary, "last_turn_id": turn_id}), turn["session_id"]),
            )
            self._emit_validated_chunks(turn_id, answer)
            self._append_chunk(turn_id, "status", "Turn abgeschlossen; Antwort ist quellengebunden und reviewpflichtig.")
            self._event(turn["case_id"], "conversation_turn_completed", "turn", turn_id, {
                "sequence_no": turn["sequence_no"], "retrieval_run_id": retrieval.get("retrieval_run_id", ""),
                "citation_count": len(citations), "correction_requested": response["correction_requested"],
            }, actor)
            coai240 = getattr(self, "_co_ai_investigator_240", None)
            if coai240 is not None:
                try:
                    assessment = coai240.assess_turn(turn_id=turn_id, actor="coai-240")
                    self._append_chunk(turn_id, "status", f"Build-240-Qualitätsgate: {assessment.get('gate','COAI_240_REVIEW')}.")
                except Exception as exc:
                    self._append_chunk(turn_id, "status", "Build-240-Qualitätsprüfung konnte nicht abgeschlossen werden: " + _text(exc, 500))
            reasoning241 = getattr(self, "_reasoning_workflow_241", None)
            if reasoning241 is not None:
                try:
                    assessment241 = reasoning241.assess_turn(turn_id=turn_id, actor="coai-241")
                    self._append_chunk(turn_id, "status", f"Build-241-Reasoning-Gate: {assessment241.get('gate','REASONING_241_REVIEW')}.")
                except Exception as exc:
                    self._append_chunk(turn_id, "status", "Build-241-Reasoning-Prüfung konnte nicht abgeschlossen werden: " + _text(exc, 500))
            return self.turn_status(turn_id=turn_id)
        except Exception as exc:
            failed = now_ts()
            self.db.execute(
                "UPDATE conversational_turns_227 SET status='failed',error_text=?,completed_at=?,updated_at=? WHERE turn_id=?",
                (_text(exc, 4000), failed, failed, turn_id),
            )
            self._append_chunk(turn_id, "error", "Turn fehlgeschlagen: " + _text(exc, 1200))
            self._event(turn["case_id"], "conversation_turn_failed", "turn", turn_id, {"error": _text(exc, 1000)}, actor)
            raise

    def _source_strategy(self, turn: Mapping[str, Any], state: Mapping[str, Any], actor: str) -> dict[str, Any]:
        target_type, target_value = self._infer_target(turn["user_message"])
        config = self.consolidation.ensure_case_config(case_id=turn["case_id"], actor=actor)
        try:
            strategy = self.source_intelligence.rank_sources(
                case_id=turn["case_id"], session_id=turn["session_id"], objective=turn["user_message"],
                target_type=target_type, target_value=target_value, language=turn["message_language"], countries=[],
                budget_class="standard", max_sources=min(int(config.get("max_source_actions") or 5), 8),
                require_independence=True, actor=actor,
                confirmation=f"SOURCE INTELLIGENCE 226 {turn['case_id']} BERECHNEN",
            )
            return {
                "query_id": strategy.get("query_id", ""), "target_type": target_type,
                "selected_sources": strategy.get("selected_sources", []),
                "query_expansions": strategy.get("query_expansions", []),
                "automatic_execution": False,
            }
        except PermissionError:
            raise
        except Exception as exc:
            return {"query_id": "", "target_type": target_type, "selected_sources": [], "query_expansions": [], "automatic_execution": False, "warning": _text(exc, 1000)}

    def _compose_prompt(
        self,
        turn: Mapping[str, Any],
        state: Mapping[str, Any],
        threads: Sequence[Mapping[str, Any]],
        hypotheses: Sequence[Mapping[str, Any]],
        source_strategy: Mapping[str, Any],
    ) -> str:
        multilingual = {}
        fusion = getattr(self, "_multilingual_fusion_v2", None)
        if fusion is not None:
            try:
                multilingual = fusion.conversation_context(case_id=turn["case_id"], limit=12)
            except Exception as exc:
                multilingual = {"warning": _text(exc, 500), "identity_candidates": [], "source_fusions": []}
        canonical = {}
        kernel = getattr(self, "_canonical_kernel_235", None)
        if kernel is not None:
            try:
                canonical = kernel.conversation_context(case_id=turn["case_id"], limit=20)
            except Exception as exc:
                canonical = {"warning": _text(exc, 500), "entities": [], "claims": [], "evidence": [], "accepted_links": [], "candidate_links_not_facts": []}
        social = {}
        social_intel = getattr(self, "_social_intelligence_v3", None)
        if social_intel is not None:
            try:
                social = social_intel.conversation_context(case_id=turn["case_id"], limit=20)
            except Exception as exc:
                social = {"warning": _text(exc, 500), "profiles_reviewed": [], "identity_candidates_reviewed_not_automatic_merges": [], "public_relationships_reviewed": [], "timeline": []}
        graph = {}
        graph_service = getattr(self, "_identity_relationship_graph_238", None)
        if graph_service is not None:
            try:
                graph = graph_service.conversation_context(case_id=turn["case_id"], limit=20)
            except Exception as exc:
                graph = {"warning": _text(exc, 500), "nodes": [], "accepted_edges": [], "candidate_edges_not_facts": []}
        coai240 = {}
        coai_service = getattr(self, "_co_ai_investigator_240", None)
        if coai_service is not None:
            try:
                coai240 = coai_service.prompt_context(case_id=turn["case_id"], limit=40)
            except Exception as exc:
                coai240 = {"warning": _text(exc, 500), "verified_claims": [], "accepted_integrity_checked_evidence": [], "contradictions": [], "open_research_gaps": []}
        reasoning241 = {}
        reasoning_service = getattr(self, "_reasoning_workflow_241", None)
        if reasoning_service is not None:
            try:
                reasoning241 = reasoning_service.workflow_context(case_id=turn["case_id"], limit=30)
            except Exception as exc:
                reasoning241 = {"warning": _text(exc, 500), "accepted_reasoning_cycles": [], "unreviewed_reasoning_cycles_not_facts": [], "prioritized_next_steps_proposals_only": [], "explicit_corrections": []}
        opsec242 = {}
        opsec_service = getattr(self, "_opsec_sentinel_242", None)
        if opsec_service is not None:
            try:
                opsec242 = opsec_service.context(turn["case_id"])
            except Exception as exc:
                opsec242 = {"warning": _text(exc, 500), "rules": ["OPSEC risk signals are not proof of an attacker."]}
        workflow245 = {}
        workflow_service = getattr(self, "_workflow245", None)
        if workflow_service is not None:
            try:
                workflow245 = workflow_service.context(turn["case_id"])
            except Exception as exc:
                workflow245 = {"warning": _text(exc, 500), "rules": ["Workflow stages are governance states, not truth states."]}
        monitoring246 = {}
        monitoring_service = getattr(self, "_monitoring246", None)
        if monitoring_service is not None:
            try:
                monitoring246 = monitoring_service.context(turn["case_id"])
            except Exception as exc:
                monitoring246 = {"warning": _text(exc, 500), "rules": ["Monitoring changes are candidates, not facts until evidence and verification gates pass."]}
        runtime247 = {}
        runtime_service = getattr(self, "_runtime247", None)
        if runtime_service is not None:
            try:
                runtime247 = runtime_service.context(turn["case_id"])
            except Exception as exc:
                runtime247 = {"warning": _text(exc, 500), "rules": ["AI runtime routing is an execution-control state, not evidence."]}
        stress249 = {}
        stress_service = getattr(self, "_stress249", None)
        if stress_service is not None:
            try:
                stress249 = stress_service.context(turn["case_id"])
            except Exception as exc:
                stress249 = {"warning": _text(exc, 500), "rules": ["Stress qualification data is operational context, not evidence."]}
        production248 = {}
        production_service = getattr(self, "_production248", None)
        if production_service is not None:
            try:
                production248 = production_service.context(turn["case_id"])
            except Exception as exc:
                production248 = {"warning": _text(exc, 500), "rules": ["Production readiness is an operational state, not evidence."]}
        influence251 = {}
        influence_service = getattr(self, "_influence251", None)
        if influence_service is not None:
            try:
                influence251 = influence_service.co_ai_context(turn["case_id"])
            except Exception as exc:
                influence251 = {"warning": _text(exc, 500), "rules": ["Influence/funding relationship candidates are not facts until independently reviewed."]}
        context = {
            "investigation_goal": state.get("investigation_goal", ""),
            "rolling_summary": state.get("conversation_summary", ""),
            "active_threads": [
                {"thread_id": x["thread_id"], "title": x["title"], "objective": x["objective"], "priority": x["priority"]}
                for x in threads[:12]
            ],
            "active_hypotheses": [
                {"hypothesis_id": x["hypothesis_id"], "text": x["hypothesis_text"], "status": x["status"],
                 "confidence": x["confidence"], "supporting_refs": _loads(x.get("supporting_refs_json"), []),
                 "contradicting_refs": _loads(x.get("contradicting_refs_json"), [])}
                for x in hypotheses[:20]
            ],
            "source_strategy": source_strategy,
            "reviewed_corrections": self._corrections(turn["session_id"]),
            "multilingual_reviewed_context": multilingual,
            "canonical_case_context_235": canonical,
            "social_intelligence_context_237": social,
            "identity_relationship_graph_context_238": graph,
            "co_ai_investigator_3_core_context_240": coai240,
            "investigative_reasoning_workflow_context_241": reasoning241,
            "opsec_sentinel_context_242": opsec242,
            "investigative_workflow_context_245": workflow245,
            "monitoring_watchlists_context_246": monitoring246,
            "production_ai_runtime_context_247": runtime247,
            "production_hardening_context_248": production248,
            "operational_stress_context_249": stress249,
            "influence_funding_context_251": influence251.get("influence_funding_context_251", influence251),
            "investigator_message": turn["user_message"],
            "instructions": [
                "Beziehe dich auf den sichtbaren Fallstand und markiere Korrekturen ausdrücklich.",
                "Behandle Hypothesen nicht als Tatsachen.",
                "Im canonical_case_context_235 gelten nur accepted_links als geprüft; candidate_links_not_facts dürfen nicht als Tatsachen formuliert werden.",
                "Nenne Gegenbelege und offene Fragen.",
                "Die Quellenstrategie ist nur ein Vorschlag; führe keine Quelle aus.",
                "Mehrsprachige Fusionen bleiben Kandidaten, bis Build 229 sie verifiziert; Transliteration allein ist kein Identitätsbeweis.",
                "Im social_intelligence_context_237 sind Cross-Platform-Matches nur reviewte Kandidaten; sie bestätigen keine Identität automatisch. Öffentliche Interaktion ist nicht automatisch eine private/persönliche Beziehung.",
                "Im identity_relationship_graph_context_238 sind nur accepted_edges geprüft; candidate_edges_not_facts sind keine Tatsachen. Graph-Nähe und Pfade beweisen weder Beziehung noch Kausalität.",
                "Nutze co_ai_investigator_3_core_context_240 als priorisierten Gesamtfallzustand: verifizierte Claims und integritätsgeprüfte akzeptierte Evidenz tragen Tatsachen; challenged/candidate/pending Einträge sind ausdrücklich Nicht-Fakten.",
                "Wenn Widersprüche oder offene Research Gaps vorhanden sind, benenne sie vor einer abschließenden Bewertung und vermeide Scheinsicherheit.",
                "Nutze investigative_reasoning_workflow_context_241 für Hypothese/Gegenhypothese, Gegenbelege, Evidenzlücken und priorisierte Prüfzüge. Ein priorisierter Schritt ist nur ein Vorschlag und darf nicht automatisch ausgeführt werden.",
                "Wenn neue akzeptierte Evidenz eine frühere Einschätzung verändert, korrigiere sie ausdrücklich statt die alte Einschätzung still zu überschreiben.",
                "Nutze opsec_sentinel_context_242 defensiv: Risikosignale sind kein Beweis für einen Tracker/Angreifer. Keine Schutzumgehung, Anti-Forensik oder autonome OS-/Netzwerkänderung; bei erhöhtem Risiko priorisiere Human-Gates und Expositionsreduktion.",
                "Nutze investigative_workflow_context_245 zur Phasenorientierung. Ein Workflow-Checkpoint oder Agenten-Work-Item ist kein Fakt und darf keine Human-, Evidence- oder OPSEC-Gates ersetzen.",
                "Nutze monitoring_watchlists_context_246 nur als Change-Detection-Kontext. Eine beobachtete Veraenderung ist bis Evidence-Vault-Review und Verifikation kein belastbarer Fakt; Monitoring autorisiert keinen autonomen Netzwerkzugriff.",
                "Nutze production_hardening_context_248 nur als Betriebs-/Readiness-Kontext. Lokales Mistral-Routing, Backup-Status oder Production-Readiness sind keine Ermittlungsbeweise; es gibt keinen stillen Cloud-Fallback und kein Unsichtbarkeitsversprechen.",
                "Nutze operational_stress_context_249 nur als Betriebsqualifikation. Stressresultate und Release-Blocker sind keine Ermittlungsbeweise und autorisieren keine externe Aktion.",
                "Im influence_funding_context_251 sind dokumentierter Fakt, institutionelle Nähe, Verdacht, behördliche Bewertung und gerichtliche Feststellung strikt getrennte Aussageklassen. Kandidaten dürfen nicht hochgestuft werden; es gibt keinen Agenten-, Loyalitäts- oder Korruptionsscore.",
            ],
        }
        return "CONVERSATIONAL_INVESTIGATOR_227_CONTEXT\n" + _canon(context)

    def _sync_ai_hypotheses(self, turn: Mapping[str, Any], answer: Mapping[str, Any], actor: str) -> None:
        existing = {x["hypothesis_text"].casefold(): x for x in self._active_hypotheses(turn["session_id"])}
        for raw in list(answer.get("hypotheses") or [])[:20]:
            if isinstance(raw, Mapping):
                text = _text(raw.get("text"), 5000).strip()
                confidence = _clamp(raw.get("confidence", 0.5))
                supports = list(raw.get("supporting_refs") or [])
                contradicts = list(raw.get("contradicting_refs") or [])
            else:
                text = _text(raw, 5000).strip(); confidence = 0.5; supports = []; contradicts = []
            if not text or text.casefold() in existing:
                continue
            self._insert_hypothesis(
                session_id=turn["session_id"], case_id=turn["case_id"], thread_id=self.ensure_state(session_id=turn["session_id"]).get("active_thread_id", ""),
                text=text, confidence=confidence, supporting_refs=supports, contradicting_refs=contradicts,
                status="unresolved", origin="local_ai_candidate", actor="local-ai",
            )

    def _save_snapshot(
        self,
        *,
        turn: Mapping[str, Any],
        summary: str,
        threads: Sequence[Mapping[str, Any]],
        hypotheses: Sequence[Mapping[str, Any]],
        retrieval: Mapping[str, Any],
        source_strategy: Mapping[str, Any],
    ) -> dict[str, Any]:
        sid, now = new_id("context227"), now_ts()
        selected_chunks = list(retrieval.get("selected_chunks") or [])
        selected_refs = list(retrieval.get("selected_refs") or [])
        config = self.consolidation.ensure_case_config(case_id=turn["case_id"], actor="context-snapshot")
        budget = {
            "max_retrieval_chunks": config.get("max_retrieval_chunks", 12),
            "selected_chunks": len(selected_chunks), "summary_chars": len(summary),
            "active_threads": len(threads), "active_hypotheses": len(hypotheses),
        }
        payload = {
            "snapshot_id": sid, "session_id": turn["session_id"], "case_id": turn["case_id"], "turn_id": turn["turn_id"],
            "summary_text": summary, "active_threads": list(threads), "active_hypotheses": list(hypotheses),
            "retrieved_sources": selected_chunks, "selected_refs": selected_refs,
            "source_strategy": dict(source_strategy), "context_budget": budget,
            "reviewed_corrections": self._corrections(turn["session_id"]), "created_at": now,
        }
        self.db.execute(
            "INSERT INTO conversational_context_snapshots_227 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (sid, turn["session_id"], turn["case_id"], turn["turn_id"], summary, dumps(list(threads)), dumps(list(hypotheses)),
             dumps(selected_chunks), dumps(selected_refs), dumps(dict(source_strategy)), dumps(budget), dumps(payload["reviewed_corrections"]), now, _hash(payload)),
        )
        return payload

    def _roll_summary(self, old: str, question: str, answer: Mapping[str, Any]) -> str:
        observations = [x.get("text", "") if isinstance(x, Mapping) else str(x) for x in (answer.get("observations") or [])[:6]]
        hypotheses = [x.get("text", "") if isinstance(x, Mapping) else str(x) for x in (answer.get("hypotheses") or [])[:4]]
        open_questions = [str(x) for x in (answer.get("open_questions") or [])[:5]]
        block = (
            f"\nErmittler: {_text(question, 1200)}\n"
            f"AI-Kernaussage: {_text(answer.get('answer'), 1800)}\n"
            f"Beobachtungen: {' | '.join(_text(x, 500) for x in observations if x)}\n"
            f"Hypothesen: {' | '.join(_text(x, 500) for x in hypotheses if x)}\n"
            f"Offene Fragen: {' | '.join(_text(x, 500) for x in open_questions if x)}\n"
        )
        merged = (_text(old, 12_000) + block).strip()
        if len(merged) > 12_000:
            merged = merged[:1500] + "\n[älterer Verlauf verdichtet]\n" + merged[-9500:]
        return merged

    def _emit_validated_chunks(self, turn_id: str, answer: Mapping[str, Any]) -> None:
        text = _text(answer.get("answer"), 40_000).strip()
        if text:
            parts = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if x.strip()]
            buffer = ""
            for part in parts:
                if len(buffer) + len(part) + 1 <= 650:
                    buffer = (buffer + " " + part).strip()
                else:
                    if buffer: self._append_chunk(turn_id, "answer", buffer)
                    buffer = part
            if buffer: self._append_chunk(turn_id, "answer", buffer)
        for section in ("observations", "inferences", "hypotheses", "open_questions", "recommended_next_steps", "translation_notes"):
            values = list(answer.get(section) or [])
            if not values:
                continue
            rendered = []
            for item in values[:20]:
                rendered.append(_text(item.get("text") if isinstance(item, Mapping) else item, 1000))
            self._append_chunk(turn_id, section, "\n".join(f"• {x}" for x in rendered if x))

    def _mark_stopped(self, turn_id: str, actor: str, phase: str, result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        now = now_ts()
        response = {"discarded_base_result": bool(result), "stop_phase": phase, "human_review_required": True}
        self.db.execute(
            "UPDATE conversational_turns_227 SET status='stopped',response_json=?,completed_at=?,updated_at=? WHERE turn_id=?",
            (dumps(response), now, now, turn_id),
        )
        self._append_chunk(turn_id, "status", f"Turn gestoppt ({phase}).")
        turn = self._turn(turn_id)
        self._event(turn["case_id"], "conversation_turn_stopped", "turn", turn_id, {"phase": phase}, actor)
        return self.turn_status(turn_id=turn_id)

    def _infer_target(self, message: str) -> tuple[str, str]:
        if match := _EMAIL_RE.search(message):
            return "email", match.group(0)
        if match := _URL_RE.search(message):
            return "url", match.group(0)
        words = [x.strip(".,;:!?()[]{}\"'") for x in message.split() if x.strip()]
        username = next((x for x in words if x.startswith("@") and len(x) > 2), "")
        if username:
            return "username", username
        lower = message.casefold()
        if any(x in lower for x in ("gmbh", "ag ", "organisation", "organization", "unternehmen", "firma", "verein")):
            return "organization", " ".join(words[-6:])[:300]
        if any(x in lower for x in ("bild", "foto", "image", "metadaten", "exif")):
            return "image", ""
        if any(x in lower for x in ("dokument", "pdf", "datei")):
            return "document", ""
        return "unknown", " ".join(words[:10])[:300]

    def _insert_hypothesis(
        self,
        *,
        session_id: str,
        case_id: str,
        thread_id: str,
        text: str,
        confidence: float,
        supporting_refs: Sequence[str],
        contradicting_refs: Sequence[str],
        status: str,
        origin: str,
        actor: str,
        supersedes: str = "",
    ) -> dict[str, Any]:
        value = _text(text, 5000).strip()
        if not value:
            raise ValueError("hypothesis text required")
        supports = self.workspace._valid_refs(case_id, list(supporting_refs))
        contradicts = self.workspace._valid_refs(case_id, list(contradicting_refs))
        if list(supporting_refs) and supports != list(supporting_refs):
            raise ValueError("invalid supporting evidence reference")
        if list(contradicting_refs) and contradicts != list(contradicting_refs):
            raise ValueError("invalid contradicting evidence reference")
        hid, now = new_id("hypothesis227"), now_ts()
        payload = {
            "hypothesis_id": hid, "session_id": session_id, "thread_id": thread_id, "case_id": case_id,
            "hypothesis_text": value, "status": status, "confidence": _clamp(confidence),
            "supporting_refs": supports, "contradicting_refs": contradicts, "origin": origin,
            "supersedes_hypothesis_id": supersedes, "created_by": actor, "created_at": now, "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO investigation_hypotheses_227 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (hid, session_id, thread_id, case_id, value, status, payload["confidence"], dumps(supports), dumps(contradicts), origin, supersedes, actor, now, now, _hash(payload)),
        )
        self._event(case_id, "hypothesis_created", "hypothesis", hid, {"status": status, "origin": origin}, actor)
        return payload

    def _create_thread_internal(self, *, session_id: str, case_id: str, title: str, objective: str, priority: int, actor: str) -> dict[str, Any]:
        title_text = _text(title, 500).strip()
        objective_text = _text(objective, 5000).strip()
        if not title_text or not objective_text:
            raise ValueError("thread title and objective required")
        tid, now = new_id("thread227"), now_ts()
        payload = {
            "thread_id": tid, "session_id": session_id, "case_id": case_id, "title": title_text,
            "objective": objective_text, "status": "active", "priority": priority, "resolution_note": "",
            "created_by": actor, "created_at": now, "updated_at": now,
        }
        self.db.execute(
            "INSERT INTO investigation_threads_227 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (tid, session_id, case_id, title_text, objective_text, "active", priority, "", actor, now, now, _hash(payload)),
        )
        self._event(case_id, "investigation_thread_created", "thread", tid, {"title": title_text, "priority": priority}, actor)
        return payload

    def _append_chunk(self, turn_id: str, chunk_type: str, content: str) -> dict[str, Any]:
        text = _text(content, 20_000).strip()
        if not text:
            return {}
        with self.db.transaction(immediate=True):
            row = self.db.one("SELECT COALESCE(MAX(sequence_no),0) AS n FROM conversational_stream_chunks_227 WHERE turn_id=?", (turn_id,)) or {"n": 0}
            sequence = int(row["n"]) + 1
            cid, now = new_id("chunk227"), now_ts()
            payload = {"chunk_id": cid, "turn_id": turn_id, "sequence_no": sequence, "chunk_type": chunk_type, "content": text, "created_at": now}
            self.db.execute("INSERT INTO conversational_stream_chunks_227 VALUES(?,?,?,?,?,?,?)", (cid, turn_id, sequence, chunk_type, text, now, _hash(payload)))
        return payload

    def _stop_requested(self, turn_id: str) -> bool:
        row = self.db.one("SELECT stop_requested FROM conversational_turns_227 WHERE turn_id=?", (turn_id,))
        return bool(row and row["stop_requested"])

    def _active_threads(self, session_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM investigation_threads_227 WHERE session_id=? AND status IN ('active','deferred') ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,priority DESC,updated_at DESC", (session_id,))

    def _active_hypotheses(self, session_id: str) -> list[dict[str, Any]]:
        return self.db.all("SELECT * FROM investigation_hypotheses_227 WHERE session_id=? AND status NOT IN ('rejected','superseded') ORDER BY updated_at DESC", (session_id,))

    def _corrections(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.db.all("SELECT correction_id,target_turn_id,correction_text,evidence_refs_json,created_by,created_at FROM conversational_corrections_227 WHERE session_id=? ORDER BY created_at DESC LIMIT 20", (session_id,))
        return [{**row, "evidence_refs": _loads(row.pop("evidence_refs_json", "[]"), [])} for row in rows]

    def _public_snapshot(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "snapshot_id": row["snapshot_id"], "session_id": row["session_id"], "case_id": row["case_id"], "turn_id": row["turn_id"],
            "summary_text": row["summary_text"], "active_threads": _loads(row["active_threads_json"], []),
            "active_hypotheses": _loads(row["active_hypotheses_json"], []), "retrieved_sources": _loads(row["retrieved_sources_json"], []),
            "selected_refs": _loads(row["selected_refs_json"], []), "source_strategy": _loads(row["source_strategy_json"], {}),
            "context_budget": _loads(row["context_budget_json"], {}),
            "reviewed_corrections": _loads(row.get("reviewed_corrections_json"), []), "created_at": row["created_at"],
        }

    def _turn(self, turn_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM conversational_turns_227 WHERE turn_id=?", (turn_id,))
        if not row:
            raise KeyError("conversation turn not found")
        return row

    def _thread(self, thread_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_threads_227 WHERE thread_id=?", (thread_id,))
        if not row:
            raise KeyError("investigation thread not found")
        return row

    def _hypothesis(self, hypothesis_id: str) -> dict[str, Any]:
        row = self.db.one("SELECT * FROM investigation_hypotheses_227 WHERE hypothesis_id=?", (hypothesis_id,))
        if not row:
            raise KeyError("hypothesis not found")
        return row

    def _case(self, case_id: str) -> None:
        if not self.db.one("SELECT case_id FROM cases WHERE case_id=?", (case_id,)):
            raise KeyError("case not found")

    def _event(self, case_id: str, event_type: str, object_type: str, object_id: str, payload: Mapping[str, Any], actor: str) -> None:
        previous = self.db.one("SELECT event_hash FROM build227_events WHERE case_id=? ORDER BY created_at DESC,event_id DESC LIMIT 1", (case_id,))
        previous_hash = (previous or {}).get("event_hash", "")
        eid, now = new_id("event227"), now_ts()
        body = {"event_id": eid, "case_id": case_id, "event_type": event_type, "object_type": object_type, "object_id": object_id, "payload": dict(payload), "actor": actor, "created_at": now, "previous_hash": previous_hash}
        event_hash = _hash(body)
        self.db.execute("INSERT INTO build227_events VALUES(?,?,?,?,?,?,?,?,?,?)", (eid, case_id, event_type, object_type, object_id, dumps(dict(payload)), actor, now, previous_hash, event_hash))
        try:
            self.audit.log(actor, event_type, object_type, object_id, case_id, dict(payload))
        except Exception:
            pass

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
