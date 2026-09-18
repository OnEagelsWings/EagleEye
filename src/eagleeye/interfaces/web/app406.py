from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app405 import create_workspace_app405

def create_workspace_app406(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app405(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build406
    app.title='EagleEye Intelligence Platform – Build 406.0 Feedback Remediation & Runtime Integration'; app.version='406.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health406():
        prev=dict(old() if callable(old) else {'ok':True}); r=ctx.build406.remediation_status(); prev.update({'build':'406.0','phase':18,'phase18_builds_completed':6,'feedback_remediation_406':True,'p1_remediation_gate_pass':r['p1_remediation_gate_pass'],'authorization_mutation_surfaces':r['catalogued_mutation_surfaces'],'next_feedback_check':'after build 407 or 408','production_release_ready':False}); return prev
    @app.get('/api/build406/remediation-status')
    def remediation_status(request:Request): auth(request); return ctx.build406.remediation_status()
    @app.get('/api/build406/phase18-status')
    def phase18_status(request:Request): auth(request); return ctx.build406.phase18_status()
    return app
create_app=create_workspace_app406
