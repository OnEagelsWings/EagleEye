from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app409 import create_workspace_app409

def create_workspace_app410(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app409(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build410
    app.title='EagleEye Intelligence Platform – Build 410.0 Feedback Qualification'; app.version='410.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health410():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build410.feedback_qualification_status(); prev.update({'build':'410.0','phase':18,'phase18_builds_completed':10,'feedback_qualification':True,'feedback_qualification_gate_pass':s['feedback_qualification_gate_pass'],'public_feedback_due':True,'feedback_cycle':'406-410','feedback_checked_before_build':True,'next_feedback_check':'before build 411','network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build410/feedback-qualification/status')
    def status(request:Request): auth(request); return ctx.build410.feedback_qualification_status()
    return app
create_app=create_workspace_app410
