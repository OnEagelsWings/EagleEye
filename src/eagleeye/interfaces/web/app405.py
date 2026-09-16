from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app400 import create_workspace_app400
from eagleeye_pro.phase18.bootstrap405 import install_phase18_405

def create_workspace_app405(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app400(base_dir=base_dir); ctx=install_phase18_405(app.state.context); team=ctx.team_identity_359
    app.title='EagleEye Intelligence Platform – Build 405.0 Source Registry v2'; app.version='405.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health405():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build405.source_registry_status(); g=ctx.build404.review_gate_status(); prev.update({'build':'405.0','phase':18,'phase18_builds_completed':5,'source_registry_v2':True,'source_registry_sources':s['sources'],'source_registry_metadata_complete':s['metadata_complete'],'ai_review_gate_pass':g['ai_review_gate_pass'],'five_build_feedback_cycle_complete':True,'public_feedback_due':True,'production_release_ready':False}); return prev
    @app.get('/api/build405/source-registry')
    def sources(request:Request): auth(request); return {'sources':ctx.build405.sources()}
    @app.get('/api/build405/source-registry/status')
    def status(request:Request): auth(request); return ctx.build405.source_registry_status()
    @app.get('/api/build405/source-registry/integrity')
    def integrity(request:Request): auth(request); return ctx.build405.source_registry_integrity()
    @app.get('/api/build405/review-gate')
    def review_gate(request:Request): auth(request); return ctx.build404.review_gate_status()
    return app
create_app=create_workspace_app405
