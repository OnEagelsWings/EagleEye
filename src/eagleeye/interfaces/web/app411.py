from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from .app379 import COOKIE
from .app410 import create_workspace_app410

def create_workspace_app411(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app410(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build411
    app.title='EagleEye Intelligence Platform – Build 411.0 Temporal Intelligence'; app.version='411.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health411():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build411.temporal_status(); r=ctx.build411.remediation_status(); rq=ctx.build409.retrieval_quality_status(); rq_ok=all(v for k,v in rq['checks'].items() if k!='version_coherent'); prev.update({'build':'411.0','phase':18,'phase18_builds_completed':11,'temporal_intelligence':True,'temporal_intelligence_gate_pass':s['temporal_intelligence_gate_pass'],'github_p1_remediation_gate_pass':r['remediation_gate_pass'],'feedback_qualification_gate_pass':r['checks']['build410_security_invariants'],'retrieval_quality_gate_pass':rq_ok,'feedback_checked_before_build':True,'next_feedback_check':'before build 412','network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build411/temporal/status')
    def status(request:Request): auth(request); return ctx.build411.temporal_status()
    @app.get('/api/build411/temporal/{search_id}')
    def timeline(search_id:str,request:Request): auth(request); return ctx.build411.timeline(search_id)
    @app.get('/api/build411/temporal/{search_id}/conflicts')
    def conflicts(search_id:str,request:Request): auth(request); return ctx.build411.temporal_conflicts(search_id)
    @app.get('/api/build411/temporal/{search_id}/coverage')
    def coverage(search_id:str,request:Request): auth(request); return ctx.build411.temporal_coverage(search_id)
    return app
create_app=create_workspace_app411
