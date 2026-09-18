from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app411 import create_workspace_app411


def create_workspace_app412(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app411(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build412
    app.title='EagleEye Intelligence Platform – Build 412.0 Relationship Intelligence Graph'; app.version='412.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req: Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health412():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build412.relationship_status(); reg=ctx.build412.registry_remediation_status(); prev.update({'build':'412.0','phase':18,'phase18_builds_completed':12,'relationship_intelligence_graph':True,'relationship_intelligence_gate_pass':s['relationship_intelligence_gate_pass'],'registry_remediation_gate_pass':reg['registry_remediation_gate_pass'],'feedback_checked_before_build':True,'next_feedback_check':'before build 413','network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build412/relationships/status')
    def status(request:Request): auth(request); return ctx.build412.relationship_status()
    @app.get('/api/build412/relationships/{search_id}')
    def graph(search_id:str,request:Request): auth(request); return ctx.build412.relationship_graph(search_id)
    @app.get('/api/build412/relationships/{search_id}/entity/{entity_id}')
    def neighborhood(search_id:str,entity_id:str,request:Request): auth(request); return ctx.build412.neighborhood(search_id,entity_id)
    @app.get('/api/build412/relationships/{search_id}/paths/{start_entity_id}/{end_entity_id}')
    def paths(search_id:str,start_entity_id:str,end_entity_id:str,request:Request,max_depth:int=4): auth(request); return ctx.build412.relationship_paths(search_id,start_entity_id,end_entity_id,max_depth)
    return app

create_app=create_workspace_app412
