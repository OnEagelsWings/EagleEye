from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app406 import create_workspace_app406

def create_workspace_app407(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app406(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build407
    app.title='EagleEye Intelligence Platform – Build 407.0 Connector/Data Fabric v1'; app.version='407.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health407():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build407.data_fabric_status(); prev.update({'build':'407.0','phase':18,'phase18_builds_completed':7,'connector_data_fabric':True,'connector_adapters':s['adapters'],'data_fabric_gate_pass':s['data_fabric_gate_pass'],'p1_remediation_gate_pass':s['checks']['build406_security_invariants'],'build406_security_invariants_pass':s['checks']['build406_security_invariants'],'next_public_feedback_build':'410.0','public_feedback_due':False,'next_feedback_check':'after build 408 at latest','network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build407/data-fabric/status')
    def status(request:Request): auth(request); return ctx.build407.data_fabric_status()
    @app.get('/api/build407/data-fabric/adapters')
    def adapters(request:Request): auth(request); return {'adapters':ctx.build407.adapters()}
    return app
create_app=create_workspace_app407
