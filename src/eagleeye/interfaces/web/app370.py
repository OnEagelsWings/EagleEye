from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app369 import COOKIE, create_workspace_app369


def _esc(v: Any)->str: return html.escape(str(v if v is not None else ""))
def _drop_route(app: FastAPI,path: str,methods:set[str])->None:
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,"path",None)==path and methods.intersection(set(getattr(r,"methods",set()) or set())))]


def create_workspace_app370(*,base_dir: str|Path|None=None)->FastAPI:
    app=create_workspace_app369(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359
    remote_enabled=bool(ctx.remote_team_364.config().get("enabled")); app.title="EagleEye Intelligence Platform – Build 370.0 Controlled Tor Gateway + Crawler Continuity"; app.version="370.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    for path,methods in [("/health",{"GET"}),("/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}),("/api/cases/{case_id}/phase16/opsec-protect",{"POST"})]: _drop_route(app,path,methods)
    def fingerprint(request:Request)->str:
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else ""))); return hashlib.sha256(material.encode()).hexdigest()
    def require_auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,""); fp=fingerprint(request); identity=team_identity.validate_session(token,client_fingerprint=fp,touch=True)
        if not identity and token and remote_enabled: ctx.build370.protect_remote_session(token=token,observed_fingerprint=fp,observed_ip=(request.client.host if request.client else ""))
        if not identity: raise HTTPException(status_code=401,detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity
    def require_case(request:Request,case_id:str,capability:str="case.read")->dict[str,Any]:
        identity=require_auth(request)
        try: ctx.build370.authorize(identity,case_id=case_id,capability=capability,object_type="tor_crawler",object_id=case_id)
        except PermissionError as exc: raise HTTPException(status_code=403,detail=str(exc))
        return identity
    @app.get("/health")
    def health370():
        payload=dict(base_health() if callable(base_health) else {"ok":True}); payload.update({"build":"370.0","phase16_builds_completed":10,"controlled_tor_gateway":True,"crawler_improvement_build":370,"continuous_crawler_expansion_370_380":True,"background_workers_started_on_boot":0,"automatic_external_connections":False,"tor_control_port_authority":False,"tor_newnym_authority":False,"production_release_ready":False}); return payload
    @app.get("/api/build370/phase16-status")
    def phase16(request:Request): require_auth(request); return ctx.build370.phase16_status()
    @app.get("/api/build370/tor-status")
    def tor_status(request:Request): require_auth(request); return ctx.build370.tor_gateway_status()
    @app.post("/api/build370/tor-config")
    async def tor_config(request:Request):
        identity=require_auth(request); body=await request.json()
        try: return ctx.build370.configure_tor_gateway(identity=identity,confirmation=str(body.get("confirmation") or ""),enabled=bool(body.get("enabled",False)),socks_host=str(body.get("socks_host") or "127.0.0.1"),socks_port=int(body.get("socks_port",9050)))
        except (ValueError,PermissionError,KeyError) as exc: raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))
    @app.post("/api/cases/{case_id}/tor370/sources/{source_id}/enqueue")
    async def tor_enqueue(case_id:str,source_id:str,request:Request):
        identity=require_case(request,case_id,"crawler.run"); body=await request.json()
        try: return ctx.build370.enqueue_tor_crawl(case_id=case_id,source_id=source_id,identity=identity,confirmation=str(body.get("confirmation") or ""))
        except (ValueError,PermissionError,RuntimeError,KeyError) as exc: raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))
    @app.get("/api/cases/{case_id}/tor370/status")
    def tor_case(case_id:str,request:Request): require_case(request,case_id,"case.read"); return ctx.build370.tor_case_status(case_id=case_id)
    @app.get("/api/build370/crawler-roadmap")
    def roadmap(request:Request): require_auth(request); return {"build":"370.0","roadmap":ctx.build370.crawler_roadmap(),"continuous":True}
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id:str,request:Request): require_case(request,case_id,"research.run"); body=await request.json(); return ctx.build370.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id:str,request:Request): require_case(request,case_id,"research.run"); return ctx.build370.autonomous_opsec_protect(case_id=case_id)
    @app.get("/api/build370/final-status")
    def final_status(request:Request): require_auth(request); return ctx.build370.dashboard()
    @app.get("/cases/{case_id}/tor-gateway")
    def console(case_id:str,request:Request):
        require_case(request,case_id,"case.read"); case=ctx.cases.get_case(case_id); st=ctx.build370.tor_case_status(case_id=case_id); gw=st["gateway"]
        roadmap_rows="".join(f"<tr><td>{x['build']}</td><td>{_esc(x['crawler_increment'])}</td></tr>" for x in ctx.build370.crawler_roadmap())
        body=f"""<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Controlled Tor Gateway · {_esc(case['title'])}</h1><p>Read-only, manuell bestätigt, case-scoped. Kein ControlPort, kein NEWNYM, keine Tor-Konfigurationsmutation.</p></div><div class='grid'><div class='card'><div class='metric'>{'ON' if gw['gateway_enabled'] else 'OFF'}</div><div>Gateway</div></div><div class='card'><div class='metric'>{st['backpressure']['case_depth']}</div><div>Tor Queue</div></div><div class='card'><div class='metric'>0</div><div>Boot-Netzwerkverbindungen</div></div></div><div class='card'><h2>Crawler-Ausbau 370–380</h2><table><tr><th>Build</th><th>messbarer Crawler-Increment</th></tr>{roadmap_rows}</table></div>"""
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Tor Gateway</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
