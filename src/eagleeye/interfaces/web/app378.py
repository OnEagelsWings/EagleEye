from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from .app377 import COOKIE, create_workspace_app377


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [
        r for r in app.router.routes
        if not (getattr(r, "path", None) == path and methods.intersection(set(getattr(r, "methods", set()) or set())))
    ]


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def create_workspace_app378(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app377(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 378.0 Voice Live Validation"
    app.version = "378.0"
    base_health = next((r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())), None)
    for path, methods in [
        ("/health", {"GET"}),
        ("/api/cases/{case_id}/phase16/autonomous-cycle", {"POST"}),
        ("/api/cases/{case_id}/phase16/opsec-protect", {"POST"}),
    ]:
        _drop(app, path, methods)

    def fp(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, "")
        fingerprint = fp(request)
        ident = team_identity.validate_session(token, client_fingerprint=fingerprint, touch=True)
        if not ident and token and remote_enabled:
            ctx.build378.protect_remote_session(token=token, observed_fingerprint=fingerprint, observed_ip=(request.client.host if request.client else ""))
        if not ident:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        ident = auth(request)
        try:
            ctx.build378.authorize(ident, case_id=case_id, capability=capability, object_type="voice_validation_v378", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return ident

    @app.get("/health")
    def health378():
        p = dict(base_health() if callable(base_health) else {"ok": True})
        p.update({
            "build": "378.0",
            "phase16_builds_completed": 18,
            "voice_live_validation": True,
            "voice_to_crawler_intent_preview": True,
            "voice_edit_reconfirmation": True,
            "voice_direct_network_authority": False,
            "voice_automatic_source_selection": False,
            "crawler_improvement_build": 378,
            "external_voice_validation": "not_run",
            "production_release_ready": False,
        })
        return p

    @app.get("/api/build378/phase16-status")
    def phase(request: Request):
        auth(request)
        return ctx.build378.phase16_status()

    @app.get("/api/build378/final-status")
    def final(request: Request):
        auth(request)
        return ctx.build378.dashboard()

    @app.post("/api/cases/{case_id}/voice378/crawler-intent/preview")
    async def voice_preview(case_id: str, request: Request):
        ident = caseauth(request, case_id, "voice.research")
        body = await request.json()
        source_ids = body.get("source_ids") or []
        if not isinstance(source_ids, list):
            raise HTTPException(400, "source_ids must be a list")
        try:
            return ctx.build378.voice_crawler_propose(
                case_id=case_id,
                identity=ident,
                transcript=str(body.get("transcript") or ""),
                source_ids=[str(x) for x in source_ids],
                source="workspace_voice378_preview",
            )
        except (PermissionError, ValueError, KeyError) as exc:
            code = 403 if isinstance(exc, PermissionError) else 400
            raise HTTPException(code, str(exc))

    @app.post("/api/cases/{case_id}/voice378/crawler-intent/{intent_id}/confirm")
    async def voice_confirm(case_id: str, intent_id: str, request: Request):
        ident = caseauth(request, case_id, "voice.research")
        body = await request.json()
        source_ids = body.get("source_ids", None)
        if source_ids is not None and not isinstance(source_ids, list):
            raise HTTPException(400, "source_ids must be a list")
        try:
            out = ctx.build378.voice_crawler_confirm(
                intent_id=intent_id,
                identity=ident,
                confirmation=str(body.get("confirmation") or ""),
                edited_transcript=(str(body.get("edited_transcript")) if body.get("edited_transcript") is not None else None),
                source_ids=([str(x) for x in source_ids] if source_ids is not None else None),
            )
        except (PermissionError, ValueError, KeyError) as exc:
            code = 403 if isinstance(exc, PermissionError) else 400
            raise HTTPException(code, str(exc))
        if str(out.get("case_id") or case_id) != case_id:
            raise HTTPException(404, "intent not in case")
        return out

    @app.post("/api/cases/{case_id}/voice378/transcribe")
    async def voice_transcribe(
        case_id: str,
        request: Request,
        audio: UploadFile = File(...),
        human_started: str = Form("false"),
        language: str = Form("de"),
        source_ids: str = Form(""),
    ):
        ident = caseauth(request, case_id, "voice.research")
        data = await audio.read(15 * 1024 * 1024 + 1)
        ids = [x.strip() for x in str(source_ids or "").split(",") if x.strip()]
        try:
            return ctx.build378.voice_crawler_transcribe(
                case_id=case_id,
                identity=ident,
                audio=data,
                media_type=audio.content_type or "",
                language=language,
                human_started=str(human_started).casefold() == "true",
                source_ids=ids,
            )
        except (PermissionError, ValueError, KeyError) as exc:
            code = 403 if isinstance(exc, PermissionError) else 400
            raise HTTPException(code, str(exc))

    @app.get("/api/cases/{case_id}/voice378/interactions")
    def voice_interactions(case_id: str, request: Request):
        caseauth(request, case_id, "voice.read")
        return {"case_id": case_id, "interactions": ctx.build378.voice_crawler_interactions(case_id=case_id, limit=100)}

    @app.get("/cases/{case_id}/voice378", response_class=HTMLResponse)
    def voice_workspace(case_id: str, request: Request):
        caseauth(request, case_id, "voice.read")
        body = f"""
        <html><head><title>Voice 378</title><style>
        body{{font-family:system-ui;margin:2rem;max-width:1000px}}textarea,input{{width:100%;padding:.6rem;margin:.3rem 0}}button{{padding:.6rem 1rem;margin:.3rem}}pre{{white-space:pre-wrap;background:#f4f4f4;padding:1rem}}
        </style></head><body>
        <p><a href='/cases/{_esc(case_id)}'>← Fall</a></p>
        <h1>Voice → Crawler Intent · Build 378</h1>
        <p>Transkript und Quellen bleiben editierbar. Jede Änderung verwirft die vorherige Bestätigung.</p>
        <label>Transkript</label><textarea id='t' rows='5' placeholder='Starte die Recherche mit den ausgewählten Quellen'></textarea>
        <label>Explizite Source-IDs, kommasepariert (max. 2)</label><input id='s'/>
        <button id='p'>Preview erzeugen</button>
        <pre id='o'></pre>
        <label>Bestätigung</label><input id='c' placeholder='VOICE CRAWL'/>
        <button id='x' disabled>Bestätigen und an Case-Workflow übergeben</button>
        <script>
        let intent=''; const out=document.getElementById('o');
        const ids=()=>document.getElementById('s').value.split(',').map(x=>x.trim()).filter(Boolean);
        async function post(u,b){{const r=await fetch(u,{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify(b)}});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Fehler');return d}}
        document.getElementById('p').onclick=async()=>{{try{{const d=await post('/api/cases/{_esc(case_id)}/voice378/crawler-intent/preview',{{transcript:document.getElementById('t').value,source_ids:ids()}});intent=d.intent_id;out.textContent=JSON.stringify(d.preview,null,2);document.getElementById('x').disabled=!d.preview.allowed_for_confirmation;}}catch(e){{out.textContent=String(e)}}}};
        document.getElementById('x').onclick=async()=>{{try{{const d=await post('/api/cases/{_esc(case_id)}/voice378/crawler-intent/'+intent+'/confirm',{{confirmation:document.getElementById('c').value,edited_transcript:document.getElementById('t').value,source_ids:ids()}});out.textContent=JSON.stringify(d,null,2);if(d.revised_intent)intent=d.revised_intent.intent_id;}}catch(e){{out.textContent=String(e)}}}};
        </script></body></html>"""
        return HTMLResponse(body)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def autonomous(case_id: str, request: Request):
        caseauth(request, case_id, "case.read")
        body = await request.json()
        return ctx.build378.run_autonomous_investigation(case_id=case_id, max_ticks=max(1, min(int(body.get("max_ticks", 8)), 20)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str, request: Request):
        caseauth(request, case_id, "case.manage")
        return ctx.build378.autonomous_opsec_protect(case_id=case_id)

    return app
