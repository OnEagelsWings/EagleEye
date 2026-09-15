from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

from eagleeye.kernel.contracts import ActionClass, AgentResult, AgentRole, AgentTask, ApprovalState, GatewayKind, ResultStatus

VOICE_POLICY = "phase15.voice-gateway.v358"
VOICE_CONTRACT = "phase15.voice-intent.v358"
MAX_AUDIO_BYTES = 15 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/wav", "audio/x-wav", "audio/ogg", "audio/mp4", "audio/mpeg"}
MANUAL_ONLY = {"export", "merge", "delete", "release"}


def _clip(value: Any, limit: int = 3000) -> str:
    return " ".join(str(value or "").split())[:limit]


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _json(value: Any, default: Any) -> Any:
    try:
        return json.loads(value) if value not in (None, "") else default
    except Exception:
        return default


class LocalWhisperAdapter358:
    """Optional offline faster-whisper adapter.

    It only accepts an existing local model path. No model download is initiated.
    Audio is written to a private temporary file and deleted immediately after
    transcription. Construction is lazy so EagleEye can run without the optional
    dependency or a configured model.
    """

    def __init__(self, model_path: str | Path | None = None) -> None:
        self.model_path = Path(model_path or os.environ.get("EAGLEEYE_WHISPER_MODEL_PATH", "")).expanduser() if (model_path or os.environ.get("EAGLEEYE_WHISPER_MODEL_PATH")) else None
        self._model = None

    @property
    def configured(self) -> bool:
        return bool(self.model_path and self.model_path.exists())

    def _load(self):
        if not self.configured:
            raise RuntimeError("local_stt_model_not_configured")
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # type: ignore
            except Exception as exc:
                raise RuntimeError("faster_whisper_not_installed") from exc
            self._model = WhisperModel(str(self.model_path), device="cpu", compute_type="int8", local_files_only=True)
        return self._model

    def __call__(self, audio: bytes, media_type: str, language: str = "de") -> str:
        suffix = ".wav" if "wav" in media_type else ".webm" if "webm" in media_type else ".ogg" if "ogg" in media_type else ".audio"
        fd, name = tempfile.mkstemp(prefix="eagleeye_voice358_", suffix=suffix)
        try:
            os.chmod(name, 0o600)
        except OSError:
            pass
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(audio); fh.flush(); os.fsync(fh.fileno())
            model = self._load()
            segments, _info = model.transcribe(name, language=language or "de", vad_filter=True, beam_size=3)
            return _clip(" ".join(str(seg.text or "").strip() for seg in segments), 12000)
        finally:
            try: os.unlink(name)
            except OSError: pass


class VoiceGateway358:
    """Push-to-talk gateway with visible transcript and explicit action confirmation."""

    def __init__(self, db: Any, *, build357: Any, task_repository: Any, cases: Any, actor: str = "local-analyst", transcriber: Callable[[bytes, str, str], str] | None = None) -> None:
        self.db = db; self.build357 = build357; self.task_repository = task_repository; self.cases = cases; self.actor = actor
        self.transcriber = transcriber if transcriber is not None else LocalWhisperAdapter358()

    def classify(self, transcript: str, mode: str = "command") -> dict[str, Any]:
        text = _clip(transcript, 12000); n = _norm(text); mode = str(mode or "command").casefold()
        if mode not in {"command", "dictation"}: raise ValueError("mode must be command or dictation")
        if mode == "dictation":
            return {"intent":"dictation", "action_class":"local_analysis", "requires_confirmation":False, "manual_ui_required":False, "summary":"Diktat übernehmen; keine externe Aktion.", "normalized_transcript":text}
        intent="question_or_note"; action="local_analysis"; confirm=False; manual=False; summary="Als Ermittlernotiz/Frage behandeln; keine externe Aktion."
        if n == "go" or n in {"go starten", "recherche go", "go recherche"}:
            intent="start_go"; action="external_research"; confirm=True; summary="Explizites GO für die bereits angelegte Intake-Recherche ausführen."
        elif any(x in n for x in ("nächste welle", "naechste welle", "weitersuchen", "recherche fortsetzen", "suche fortsetzen", "crawler weiter")):
            intent="continue_research_wave"; action="external_research"; confirm=True; summary="Terminale Research-Wave auswerten und – nur wenn zulässig – eine begrenzte Folge-Wave erzeugen."
        elif any(x in n for x in ("starte suche", "starte recherche", "crawler starten", "suche starten")):
            intent="start_or_continue_research"; action="external_research"; confirm=True; summary="Governte Recherche starten/fortsetzen; ohne aktives GO wird nicht ausgeführt."
        elif "crawler" in n and any(x in n for x in ("status", "stand", "überwach", "ueberwach", "monitor")):
            intent="crawler_status"; summary="Crawler-, Job- und OPSEC-Status lesen; keine externe Aktion."
        elif any(x in n for x in ("dossier aktual", "dossier erstellen", "dossier neu", "dossier bauen")):
            intent="refresh_dossier"; summary="Fallweit fusionieren und Dossier lokal neu erzeugen."
        elif any(x in n for x in ("briefing", "vorlesen", "lies vor", "sprich")):
            intent="briefing"; summary="Aktuelles Dossier/Briefing lokal bereitstellen."
        elif any(x in n for x in ("export", "exportieren")):
            intent="export"; action="export"; confirm=True; manual=True; summary="Export erkannt; Voice darf ihn nicht direkt ausführen. Manuelle UI-Freigabe erforderlich."
        elif any(x in n for x in ("zusammenführen", "zusammenfuehren", "merge", "identität bestätigen", "identitaet bestaetigen")):
            intent="merge"; action="merge"; confirm=True; manual=True; summary="Merge/Identitätsaktion erkannt; Voice darf sie nicht direkt ausführen."
        elif any(x in n for x in ("löschen", "lösche", "loeschen", "loesche", "delete")):
            intent="delete"; action="delete"; confirm=True; manual=True; summary="Löschaktion erkannt; Voice darf sie nicht direkt ausführen."
        elif any(x in n for x in ("freigeben", "veröffentlichen", "veröffentliche", "veroeffentlichen", "veroeffentliche", "release")):
            intent="release"; action="release"; confirm=True; manual=True; summary="Release/Freigabe erkannt; Voice darf sie nicht direkt ausführen."
        return {"intent":intent,"action_class":action,"requires_confirmation":confirm,"manual_ui_required":manual,"summary":summary,"normalized_transcript":text}

    @staticmethod
    def _contract_enums(action: str, confirm: bool) -> tuple[ActionClass, GatewayKind, ApprovalState]:
        amap={"local_analysis":ActionClass.LOCAL_ANALYSIS,"external_research":ActionClass.EXTERNAL_RESEARCH,"export":ActionClass.EXPORT,"merge":ActionClass.MERGE,"delete":ActionClass.DELETE,"release":ActionClass.RELEASE}
        gmap={"external_research":GatewayKind.SEARCH,"export":GatewayKind.EXPORT,"merge":GatewayKind.MUTATION,"delete":GatewayKind.MUTATION,"release":GatewayKind.MUTATION}
        return amap[action], gmap.get(action, GatewayKind.NONE), ApprovalState.PENDING if confirm else ApprovalState.NOT_REQUIRED

    def propose_transcript(self, *, case_id: str, transcript: str, mode: str = "command", source: str = "typed") -> dict[str, Any]:
        self.cases.get_case(case_id)
        classified=self.classify(transcript, mode)
        ac,gw,ap=self._contract_enums(classified["action_class"], classified["requires_confirmation"])
        task=AgentTask.create(case_id=case_id, actor=self.actor, agent_role=AgentRole.VOICE_GATEWAY, action_class=ac, requested_gateway=gw, approval_state=ap, input_payload={
            "kind":"voice_intent_v358","voice_contract":VOICE_CONTRACT,"mode":mode,"transcript":classified["normalized_transcript"],"source":source,
            "intent":classified["intent"],"intent_summary":classified["summary"],"requires_confirmation":classified["requires_confirmation"],"manual_ui_required":classified["manual_ui_required"],
            "audio_persisted":False,"always_on_microphone":False,"voice_biometrics":False,"policy_version":VOICE_POLICY,
        })
        saved=self.task_repository.create_task(task)
        return {"intent_id":task.task_id,"case_id":case_id,**classified,"source":source,"audio_persisted":False,"task":saved}

    def transcribe_push_to_talk(self, *, case_id: str, audio: bytes, media_type: str, language: str = "de", human_started: bool = False, mode: str = "command") -> dict[str, Any]:
        self.cases.get_case(case_id)
        if not human_started: raise PermissionError("push_to_talk_human_start_required")
        if not audio: raise ValueError("audio required")
        if len(audio) > MAX_AUDIO_BYTES: raise ValueError("audio too large")
        mt=str(media_type or "").split(";",1)[0].casefold()
        if mt not in ALLOWED_AUDIO_TYPES: raise ValueError("unsupported audio media type")
        try:
            text=self.transcriber(audio, mt, language) if callable(self.transcriber) else ""
        except RuntimeError as exc:
            return {"status":str(exc),"transcript":"","audio_persisted":False,"audio_deleted_after_transcription":True,"requires_manual_transcript":True,"network_used_by_voice_gateway":False}
        if not _clip(text):
            return {"status":"no_speech_recognized","transcript":"","audio_persisted":False,"audio_deleted_after_transcription":True,"requires_manual_transcript":True,"network_used_by_voice_gateway":False}
        proposed=self.propose_transcript(case_id=case_id, transcript=text, mode=mode, source="push_to_talk_local_stt")
        return {"status":"transcribed","transcript":text,"audio_persisted":False,"audio_deleted_after_transcription":True,"requires_manual_transcript":False,"network_used_by_voice_gateway":False,**proposed}

    def _intent_task(self, intent_id: str) -> dict[str, Any]:
        row=self.db.one("SELECT task_json FROM phase15_agent_tasks WHERE task_id=? AND agent_role='voice_gateway'", (intent_id,))
        if not row: raise KeyError(intent_id)
        return _json(row.get("task_json"), {})

    def execute(self, *, intent_id: str, confirmed: bool = False, edited_transcript: str | None = None) -> dict[str, Any]:
        task=self._intent_task(intent_id); p=task.get("input_payload") or {}; case_id=str(task.get("case_id") or "")
        if edited_transcript is not None and _clip(edited_transcript) != _clip(p.get("transcript")):
            revised=self.propose_transcript(case_id=case_id, transcript=edited_transcript, mode=str(p.get("mode") or "command"), source="edited_transcript")
            if revised["requires_confirmation"] and not confirmed:
                return {"state":"confirmation_required","revised_intent":revised,"executed":False}
            return self.execute(intent_id=revised["intent_id"], confirmed=confirmed)
        intent=str(p.get("intent") or "question_or_note")
        if bool(p.get("manual_ui_required")):
            state="manual_ui_required"; output={"intent":intent,"state":state,"executed":False,"reason":"voice_cannot_execute_irreversible_or_release_action"}
        elif bool(p.get("requires_confirmation")) and not confirmed:
            output={"intent":intent,"state":"confirmation_required","executed":False}
        elif intent=="start_go":
            output={"intent":intent,"state":"executed","executed":True,"result":self.build357.start_investigation_go(case_id=case_id,go="GO")}
        elif intent in {"continue_research_wave","start_or_continue_research"}:
            if not self.build357.active_investigation_go(case_id):
                output={"intent":intent,"state":"go_required","executed":False}
            else:
                output={"intent":intent,"state":"executed","executed":True,"result":self.build357.evaluate_investigation_wave(case_id=case_id,allow_followup=True)}
        elif intent=="crawler_status":
            output={"intent":intent,"state":"executed_read_only","executed":True,"result":self.build357.monitor_investigation_crawler(case_id)}
        elif intent=="refresh_dossier":
            output={"intent":intent,"state":"executed_local","executed":True,"result":self.build357.investigation_supervisor_tick(case_id=case_id)}
        elif intent=="briefing":
            d=self.build357.latest_investigation_dossier(case_id) or self.build357.build_investigation_dossier(case_id=case_id)
            output={"intent":intent,"state":"executed_local","executed":True,"result":{"report_id":d.get("report_id"),"speech_text":d.get("speech_text",""),"executive_summary":d.get("executive_summary","")}}
        else:
            output={"intent":intent,"state":"transcript_ready_for_human_use","executed":False,"transcript":p.get("transcript","")}
        result=AgentResult.create(task_id=intent_id,status=ResultStatus.COMPLETED if output.get("executed") else ResultStatus.DEFERRED,output_payload={**output,"confirmed":bool(confirmed),"policy_version":VOICE_POLICY,"network_used_by_voice_gateway":False},gateway_used=GatewayKind.NONE,policy_reason=str(output.get("state") or "voice_intent_processed"))
        saved=self.task_repository.append_result(result)
        return {**output,"result_record":saved,"network_used_by_voice_gateway":False}

    def interactions(self, case_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows=self.db.all("SELECT task_id,task_json,created_at FROM phase15_agent_tasks WHERE case_id=? AND agent_role='voice_gateway' ORDER BY created_at DESC LIMIT ?", (case_id,max(1,min(int(limit),200))))
        out=[]
        for row in rows:
            task=_json(row.get("task_json"),{}); results=self.task_repository.list_results(str(row.get("task_id") or "")); p=task.get("input_payload") or {}
            out.append({"intent_id":row.get("task_id"),"created_at":row.get("created_at"),"mode":p.get("mode"),"transcript":p.get("transcript"),"intent":p.get("intent"),"intent_summary":p.get("intent_summary"),"requires_confirmation":bool(p.get("requires_confirmation")),"manual_ui_required":bool(p.get("manual_ui_required")),"latest_result":results[-1] if results else None})
        return out

    def status(self) -> dict[str, Any]:
        configured=bool(getattr(self.transcriber,"configured",False)) if not callable(self.transcriber) or hasattr(self.transcriber,"configured") else True
        return {"voice_policy":VOICE_POLICY,"voice_contract":VOICE_CONTRACT,"push_to_talk":True,"always_on_microphone":False,"visible_editable_transcript":True,"command_and_dictation_modes":True,"confirmation_for_external_research":True,"manual_ui_for_export_merge_delete_release":True,"audio_persisted_by_default":False,"audio_deleted_after_transcription":True,"voice_biometrics":False,"direct_network_client":False,"local_stt_model_configured":configured,"local_stt_live_validated":False}
