from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app368 import COOKIE, create_workspace_app368


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop_route(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [r for r in app.router.routes if not (getattr(r,"path",None)==path and methods.intersection(set(getattr(r,"methods",set()) or set())))]


def create_workspace_app369(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app368(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359
    remote_enabled=bool(ctx.remote_team_364.config().get("enabled")); app.title="EagleEye Intelligence Platform – Build 369.0 Crawler Production"; app.version="369.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    _drop_route(app,"/health",{"GET"}); _drop_route(app,"/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}); _drop_route(app,"/api/cases/{case_id}/phase16/opsec-protect",{"POST"})

    def fingerprint(request: Request)->str:
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")))
        return hashlib.sha256(material.encode("utf-8",errors="replace")).hexdigest()
    def require_auth(request: Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,""); fp=fingerprint(request); identity=team_identity.validate_session(token,client_fingerprint=fp,touch=True)
        if not identity and token and remote_enabled: ctx.build369.protect_remote_session(token=token,observed_fingerprint=fp,observed_ip=(request.client.host if request.client else ""))
        if not identity: raise HTTPException(status_code=401,detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity
    def require_case(request: Request,case_id: str,capability: str="case.read")->dict[str,Any]:
        identity=require_auth(request)
        try: ctx.build369.authorize(identity,case_id=case_id,capability=capability,object_type="crawler_production",object_id=case_id)
        except PermissionError as exc: raise HTTPException(status_code=403,detail=str(exc))
        return identity

    @app.get("/health")
    def health369():
        payload=dict(base_health() if callable(base_health) else {"ok":True}); payload.update({"build":"369.0","phase16_builds_completed":9,"crawler_production":True,"production_scheduler":True,"background_workers_started_on_boot":0,"automatic_external_connections":False,"provider_connector_live_gate_bypass":False,"darknet_recurring_scheduler":False,"production_release_ready":False}); return payload

    @app.get("/api/build369/phase16-status")
    def phase16_status(request: Request): require_auth(request); return ctx.build369.phase16_status()
    @app.get("/api/cases/{case_id}/crawler369/status")
    def case_status(case_id: str,request: Request): require_case(request,case_id,"case.read"); return {"backpressure":ctx.build369.crawler_backpressure(case_id=case_id),"soak":ctx.build369.crawler_soak_snapshot(case_id=case_id),"readiness":ctx.build369.crawler_production_readiness(case_id=case_id)}
    @app.post("/api/cases/{case_id}/crawler369/sources/{source_id}/schedule")
    async def configure(case_id: str,source_id: str,request: Request):
        identity=require_case(request,case_id,"crawler.run"); body=await request.json()
        try: return ctx.build369.configure_crawler_schedule(case_id=case_id,source_id=source_id,identity=identity,confirmation=str(body.get("confirmation") or ""),interval_minutes=int(body.get("interval_minutes",60)),enabled=bool(body.get("enabled",True)),failure_threshold=int(body.get("failure_threshold",3)),max_backoff_minutes=int(body.get("max_backoff_minutes",1440)),case_high_watermark=int(body.get("case_high_watermark",8)),global_high_watermark=int(body.get("global_high_watermark",64)))
        except (ValueError,KeyError,PermissionError) as exc: raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))
    @app.post("/api/cases/{case_id}/crawler369/scheduler-tick")
    async def tick(case_id: str,request: Request): identity=require_case(request,case_id,"crawler.run"); return ctx.build369.crawler_scheduler_tick(case_id=case_id,identity=identity)
    @app.get("/api/cases/{case_id}/crawler369/soak")
    def soak(case_id: str,request: Request,limit: int=200): require_case(request,case_id,"case.read"); return ctx.build369.crawler_soak_snapshot(case_id=case_id,limit=limit)
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id: str,request: Request): require_case(request,case_id,"research.run"); body=await request.json(); return ctx.build369.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str,request: Request): require_case(request,case_id,"research.run"); return ctx.build369.autonomous_opsec_protect(case_id=case_id)
    @app.get("/api/build369/final-status")
    def final_status(request: Request): require_auth(request); return ctx.build369.dashboard()

    @app.get("/cases/{case_id}/crawler-production")
    def console(case_id: str,request: Request):
        require_case(request,case_id,"case.read"); case=ctx.cases.get_case(case_id); soak=ctx.build369.crawler_soak_snapshot(case_id=case_id); pressure=soak["backpressure"]
        sources=soak["scheduled_sources"]
        rows="".join(f"<tr><td><code>{_esc(s['source_id'])}</code></td><td>{_esc(s['source_health'])}</td><td>{'offen' if s['circuit_open'] else 'geschlossen'}</td><td>{_esc(s['next_due_at'])}</td></tr>" for s in sources) or "<tr><td colspan='4' class='muted'>Keine wiederkehrend freigegebenen Quellen.</td></tr>"
        body=f"""<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Crawler Production · {_esc(case['title'])}</h1><p class='muted'>Scheduling, Backpressure, Source Health, Delta/Resume und Lease-Stabilität.</p></div><div class='grid'><div class='card'><div class='metric'>{soak['runs']}</div><div>Runs</div></div><div class='card'><div class='metric'>{soak['succeeded']}</div><div>erfolgreich</div></div><div class='card'><div class='metric'>{pressure['case_crawl_queue_depth']}</div><div>Case Queue</div></div><div class='card'><div class='metric'>{soak['open_source_circuits']}</div><div>offene Source Circuits</div></div></div><div class='card'><h2>Produktionsgrenzen</h2><p>Scheduler-Ticks sind explizit orchestriert; beim Start werden 0 Hintergrundworker und 0 externe Verbindungen erzeugt.</p><p>Provider-Connectoren behalten ihre jeweiligen LIVE-Gates. Darknet-Quellen werden nicht wiederkehrend durch Build 369 geplant.</p></div><div class='card'><h2>Scheduled Sources</h2><table><tr><th>Source</th><th>Health</th><th>Circuit</th><th>Next due</th></tr>{rows}</table></div>"""
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem}code{background:#eef2f7;padding:2px 5px;border-radius:4px}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Crawler Production</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
