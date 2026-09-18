from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app407 import create_workspace_app407

def create_workspace_app408(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app407(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build408
    app.title='EagleEye Intelligence Platform – Build 408.0 Federated Search v1'; app.version='408.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health408():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build408.federated_search_status(); prev.update({'build':'408.0','phase':18,'phase18_builds_completed':8,'federated_search':True,'federated_search_gate_pass':s['federated_search_gate_pass'],'data_fabric_gate_pass':s['checks']['build407_security_invariants'],'source_health_history_integrity':s['checks']['source_health_history_integrity'],'feedback_checked_before_build':True,'next_feedback_check':'before build 409','next_public_feedback_build':'410.0','public_feedback_due':False,'network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build408/federated-search/status')
    def status(request:Request): auth(request); return ctx.build408.federated_search_status()
    return app
create_app=create_workspace_app408
