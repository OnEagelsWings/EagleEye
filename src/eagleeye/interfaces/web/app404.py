from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app403 import create_workspace_app403

def create_workspace_app404(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app403(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build404
    app.title='EagleEye Intelligence Platform – Build 404.0 AI Review Gate'; app.version='404.0'
    old_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest()
        identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health404():
        prev=dict(old_health() if callable(old_health) else {'ok':True}); g=ctx.build404.review_gate_status()
        prev.update({'build':'404.0','phase':18,'phase18_builds_completed':4,'ai_review_gate':True,'ai_review_gate_pass':g['ai_review_gate_pass'],'open_blocking_ai_findings':g['open_blocking_count'],'next_public_feedback_build':'405.0','production_release_ready':False}); return prev
    @app.get('/api/build404/review-rules')
    def rules(request:Request): auth(request); return ctx.build404.review_rules()
    @app.get('/api/build404/review-gate')
    def gate(request:Request): auth(request); return ctx.build404.review_gate_status()
    @app.get('/api/build404/review-integrity')
    def integrity(request:Request): auth(request); return ctx.build404.review_integrity()
    return app
create_app=create_workspace_app404
