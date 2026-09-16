from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app402 import create_workspace_app402

def create_workspace_app403(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app402(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build403
    app.title="EagleEye Intelligence Platform – Build 403.0 Negative Path & Abuse Framework"; app.version="403.0"
    old_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health403():
        prev=dict(old_health() if callable(old_health) else {'ok':True}); n=ctx.build403.negative_path_status(); prev.update({'build':'403.0','phase':18,'phase18_builds_completed':3,'negative_path_framework':n['negative_path_framework_ready'],'negative_path_scenarios':n['scenario_count'],'next_public_feedback_build':'405.0','production_release_ready':False}); return prev
    @app.get('/api/build403/negative-path-catalog')
    def catalog(request:Request): auth(request); return ctx.build403.negative_path_catalog()
    @app.get('/api/build403/negative-path-audit')
    def audit(request:Request): auth(request); return ctx.build403.negative_path_audit()
    @app.get('/api/build403/negative-path-status')
    def status(request:Request): auth(request); return ctx.build403.negative_path_status()
    return app
create_app=create_workspace_app403
