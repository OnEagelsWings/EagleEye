from __future__ import annotations
import hashlib, html
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from .app370 import COOKIE, create_workspace_app370

def _esc(v:Any)->str:return html.escape(str(v if v is not None else ""))
def _drop(app:FastAPI,path:str,methods:set[str])->None:app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,"path",None)==path and methods.intersection(set(getattr(r,"methods",set()) or set())))]

def create_workspace_app371(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app370(base_dir=base_dir);ctx=app.state.context;team_identity=ctx.team_identity_359;remote_enabled=bool(ctx.remote_team_364.config().get("enabled"));app.title="EagleEye Intelligence Platform – Build 371.0 Entity Resolution v2";app.version="371.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    for path,methods in [("/health",{"GET"}),("/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}),("/api/cases/{case_id}/phase16/opsec-protect",{"POST"})]:_drop(app,path,methods)
    def fp(request:Request)->str:
        m="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")));return hashlib.sha256(m.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,"");f=fp(request);ident=team_identity.validate_session(token,client_fingerprint=f,touch=True)
        if not ident and token and remote_enabled:ctx.build371.protect_remote_session(token=token,observed_fingerprint=f,observed_ip=(request.client.host if request.client else ""))
        if not ident:raise HTTPException(401,"Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident
    def caseauth(request:Request,case_id:str,capability:str="case.read")->dict[str,Any]:
        ident=auth(request)
        try:ctx.build371.authorize(ident,case_id=case_id,capability=capability,object_type="entity_resolution_v2",object_id=case_id)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        return ident
    @app.get("/health")
    def health371():
        p=dict(base_health() if callable(base_health) else {"ok":True});p.update({"build":"371.0","phase16_builds_completed":11,"entity_resolution_v2":True,"crawler_improvement_build":371,"entity_linked_crawl_provenance":True,"source_to_entity_lead_queue":True,"continuous_crawler_expansion_370_380":True,"automatic_identity_merge":False,"production_release_ready":False});return p
    @app.get("/api/build371/phase16-status")
    def phase(request:Request):auth(request);return ctx.build371.phase16_status()
    @app.get("/api/cases/{case_id}/entity371/status")
    def estatus(case_id:str,request:Request):caseauth(request,case_id);return {"entity":ctx.build371.entity_case_status(case_id=case_id),"crawler_leads":ctx.build371.entity_lead_case_status(case_id=case_id)}
    @app.post("/api/cases/{case_id}/entity371/compare")
    async def compare(case_id:str,request:Request):
        ident=caseauth(request,case_id,"research.run");body=await request.json()
        try:return ctx.build371.compare_entities_v2(case_id=case_id,left_entity_id=str(body.get("left_entity_id") or ""),right_entity_id=str(body.get("right_entity_id") or ""),identity=ident)
        except (ValueError,KeyError,PermissionError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.post("/api/cases/{case_id}/entity371/crawl-lead")
    async def lead(case_id:str,request:Request):
        ident=caseauth(request,case_id,"research.run");body=await request.json()
        try:return ctx.build371.enqueue_entity_link_lead(case_id=case_id,crawl_run_id=str(body.get("crawl_run_id") or ""),fetch_id=str(body.get("fetch_id") or "") or None,target_entity_id=str(body.get("target_entity_id") or ""),candidate_entity_id=str(body.get("candidate_entity_id") or ""),identity=ident,rationale=str(body.get("rationale") or ""))
        except (ValueError,KeyError,PermissionError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id:str,request:Request):caseauth(request,case_id,"research.run");body=await request.json();return ctx.build371.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id:str,request:Request):caseauth(request,case_id,"research.run");return ctx.build371.autonomous_opsec_protect(case_id=case_id)
    @app.get("/api/build371/final-status")
    def final(request:Request):auth(request);return ctx.build371.dashboard()
    @app.get("/cases/{case_id}/entity-resolution-v2")
    def console(case_id:str,request:Request):
        caseauth(request,case_id);case=ctx.cases.get_case(case_id);er=ctx.build371.entity_case_status(case_id=case_id);leads=ctx.build371.entity_lead_case_status(case_id=case_id)
        body=f"""<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Entity Resolution v2 · {_esc(case['title'])}</h1><p>Evidence-weighted, source-aware, review-gated. Scores sind keine Identitätswahrscheinlichkeiten.</p></div><div class='grid'><div class='card'><div class='metric'>{er['entities']}</div><div>Entity candidates</div></div><div class='card'><div class='metric'>{er['unresolved_review_items']}</div><div>Review items</div></div><div class='card'><div class='metric'>{len(leads['lead_jobs'])}</div><div>Crawler→Entity leads</div></div></div><div class='card'><h2>Hard boundaries</h2><ul><li>Strong identifier conflicts veto same-entity inference.</li><li>Common names receive a collision penalty.</li><li>Independent sources increase review priority, not certainty.</li><li>No automatic merge or identity confirmation.</li></ul></div>"""
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1100px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}a{color:#1d4ed8;text-decoration:none}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Entity Resolution v2</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
