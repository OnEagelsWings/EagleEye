from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .app373 import COOKIE, create_workspace_app373


def _esc(v: Any) -> str:
    return html.escape(str(v if v is not None else ""))


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r,"path",None)==path and methods.intersection(set(getattr(r,"methods",set()) or set())))]


def create_workspace_app374(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app373(base_dir=base_dir);ctx=app.state.context;team_identity=ctx.team_identity_359;remote_enabled=bool(ctx.remote_team_364.config().get("enabled"));app.title="EagleEye Intelligence Platform – Build 374.0 Case Workflow";app.version="374.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    for path,methods in [
        ("/health",{"GET"}),("/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}),("/api/cases/{case_id}/phase16/opsec-protect",{"POST"}),
        ("/api/cases/{case_id}/graph373/navigation-plan",{"POST"}),("/api/cases/{case_id}/graph373/navigate",{"POST"}),
        ("/cases/{case_id}/crawler/{source_id}/enqueue",{"POST"}),
    ]:_drop(app,path,methods)
    def fp(request:Request)->str:
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")));return hashlib.sha256(material.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,"");fingerprint=fp(request);ident=team_identity.validate_session(token,client_fingerprint=fingerprint,touch=True)
        if not ident and token and remote_enabled:ctx.build374.protect_remote_session(token=token,observed_fingerprint=fingerprint,observed_ip=(request.client.host if request.client else ""))
        if not ident:raise HTTPException(401,"Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident
    def caseauth(request:Request,case_id:str,capability:str="case.read")->dict[str,Any]:
        ident=auth(request)
        try:ctx.build374.authorize(ident,case_id=case_id,capability=capability,object_type="case_workflow_v374",object_id=case_id)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        return ident
    @app.get("/health")
    def health374():
        p=dict(base_health() if callable(base_health) else {"ok":True});p.update({"build":"374.0","phase16_builds_completed":14,"case_workflow":True,"source_request_budgets":True,"workflow_pause_resume":True,"analyst_handoff":True,"crawler_improvement_build":374,"continuous_crawler_expansion_370_380":True,"production_release_ready":False});return p
    @app.get("/api/build374/phase16-status")
    def phase(request:Request):auth(request);return ctx.build374.phase16_status()
    @app.get("/api/build374/final-status")
    def final(request:Request):auth(request);return ctx.build374.dashboard()
    @app.post("/api/cases/{case_id}/workflow374/configure")
    async def configure(case_id:str,request:Request):
        ident=caseauth(request,case_id,"case.manage");body=await request.json()
        try:return ctx.build374.configure_case_workflow(case_id=case_id,identity=ident,source_budgets=dict(body.get("source_budgets") or {}),case_request_budget=int(body.get("case_request_budget",100)),max_active_crawls=int(body.get("max_active_crawls",3)),confirmation=str(body.get("confirmation") or ""))
        except (PermissionError,ValueError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.get("/api/cases/{case_id}/workflow374/status")
    def workflow_status(case_id:str,request:Request):return ctx.build374.case_workflow_status(case_id=case_id,identity=caseauth(request,case_id,"crawler.monitor"))
    @app.post("/api/cases/{case_id}/workflow374/pause")
    async def pause(case_id:str,request:Request):
        ident=caseauth(request,case_id,"case.manage");body=await request.json()
        try:return ctx.build374.pause_case_workflow(case_id=case_id,identity=ident,reason=str(body.get("reason") or ""),confirmation=str(body.get("confirmation") or ""))
        except (PermissionError,ValueError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.post("/api/cases/{case_id}/workflow374/resume")
    async def resume(case_id:str,request:Request):
        ident=caseauth(request,case_id,"case.manage");body=await request.json()
        try:return ctx.build374.resume_case_workflow(case_id=case_id,identity=ident,confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:raise HTTPException(403,str(exc))
    @app.post("/api/cases/{case_id}/workflow374/handoff")
    async def handoff(case_id:str,request:Request):
        ident=caseauth(request,case_id,"case.manage");body=await request.json()
        try:return ctx.build374.handoff_case_workflow(case_id=case_id,identity=ident,to_username=str(body.get("to_username") or ""),note=str(body.get("note") or ""),confirmation=str(body.get("confirmation") or ""))
        except (PermissionError,ValueError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.post("/api/cases/{case_id}/workflow374/handoff/accept")
    async def accept(case_id:str,request:Request):
        ident=caseauth(request,case_id,"crawler.run");body=await request.json()
        try:return ctx.build374.accept_case_handoff(case_id=case_id,identity=ident,confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:raise HTTPException(403,str(exc))
    @app.post("/api/cases/{case_id}/workflow374/complete")
    async def complete(case_id:str,request:Request):
        ident=caseauth(request,case_id,"case.manage");body=await request.json()
        try:return ctx.build374.complete_case_workflow(case_id=case_id,identity=ident,note=str(body.get("note") or ""),confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:raise HTTPException(403,str(exc))
    @app.post("/api/cases/{case_id}/graph373/navigation-plan")
    async def nav_plan(case_id:str,request:Request):
        ident=caseauth(request,case_id,"crawler.run");body=await request.json()
        try:return ctx.build374.workflow_navigation_plan(case_id=case_id,root_entity_id=str(body.get("root_entity_id") or ""),source_ids=list(body.get("source_ids") or []),identity=ident)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc))
    @app.post("/api/cases/{case_id}/graph373/navigate")
    async def navigate(case_id:str,request:Request):
        ident=caseauth(request,case_id,"crawler.run");body=await request.json()
        try:return ctx.build374.workflow_navigate(case_id=case_id,root_entity_id=str(body.get("root_entity_id") or ""),source_ids=list(body.get("source_ids") or []),identity=ident,confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc))
    @app.post("/api/cases/{case_id}/workflow374/crawler/{source_id}/enqueue")
    async def workflow_enqueue(case_id:str,source_id:str,request:Request):
        ident=caseauth(request,case_id,"crawler.run");body=await request.json()
        try:return ctx.build374.workflow_enqueue_source(case_id=case_id,source_id=source_id,identity=ident,confirmation=str(body.get("confirmation") or ""))
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except KeyError as exc:raise HTTPException(400,str(exc))
    @app.post("/cases/{case_id}/crawler/{source_id}/enqueue")
    def legacy_enqueue(case_id:str,source_id:str,request:Request,confirmation:str=Form("")):
        ident=caseauth(request,case_id,"crawler.run")
        try:ctx.build374.workflow_enqueue_source(case_id=case_id,source_id=source_id,identity=ident,confirmation=confirmation)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        return RedirectResponse(f"/cases/{case_id}/workflow374",status_code=303)
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id:str,request:Request):caseauth(request,case_id,"research.run");body=await request.json();return ctx.build374.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id:str,request:Request):caseauth(request,case_id,"research.run");return ctx.build374.autonomous_opsec_protect(case_id=case_id)
    @app.get("/cases/{case_id}/workflow374")
    def workflow_page(case_id:str,request:Request):
        ident=caseauth(request,case_id,"crawler.monitor");case=ctx.cases.get_case(case_id)
        try:st=ctx.build374.case_workflow_status(case_id=case_id,identity=ident)
        except KeyError:st=None
        if not st:body=f"<h1>Case Workflow · {_esc(case['title'])}</h1><p>No workflow configured.</p><p>Configure via the authenticated Build-374 API after defining reviewed sources and source budgets.</p>"
        else:
            u=st['usage'];rows=''.join(f"<tr><td><code>{_esc(s)}</code></td><td>{_esc(limit)}</td><td>{_esc(u['by_source'].get(s,{}).get('reserved',0))}</td><td>{_esc(u['source_remaining_requests'].get(s,limit))}</td></tr>" for s,limit in st['source_budgets'].items())
            h=st.get('handoff') or {};body=f"<p><a href='/cases/{_esc(case_id)}'>← Case</a></p><h1>Case Workflow · {_esc(case['title'])}</h1><section class='card'><b>State:</b> {_esc(st['state'])} · <b>Owner:</b> {_esc(st['current_owner'])}<br><b>Workflow:</b> <code>{_esc(st['workflow_id'])}</code></section><section class='card'><h2>Case budget</h2><p>{u['case_reserved_requests']} reserved / {st['case_request_budget']} max · {u['case_remaining_requests']} remaining · active crawls {u['active_crawls']}/{st['max_active_crawls']}</p></section><section class='card'><h2>Source budgets</h2><table><tr><th>Source</th><th>Limit</th><th>Reserved</th><th>Remaining</th></tr>{rows}</table></section><section class='card'><h2>Pause / Handoff</h2><p>Paused jobs: {len(st['paused_job_ids'])} · draining jobs: {len(st['draining_job_ids'])}</p><p>Handoff: {_esc(h.get('status','none'))} {_esc(h.get('from',''))} → {_esc(h.get('to',''))}</p></section><section class='card'><p>No autonomous scope expansion. Running workers are drained, not force-killed. Handoff requires target acceptance.</p></section>"
        css="body{font-family:system-ui,-apple-system,sans-serif;background:#f5f7fa;color:#18202a;margin:0}main{max-width:1100px;margin:30px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #e5e7eb;text-align:left}code{font-size:.82rem}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Case Workflow</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
