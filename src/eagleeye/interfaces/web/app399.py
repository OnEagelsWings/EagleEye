from __future__ import annotations
import hashlib
from pathlib import Path
from fastapi import FastAPI,HTTPException,Request
from .app379 import COOKIE
from .app398 import create_workspace_app398
from eagleeye_pro.phase17.target_soak399 import CONFIRM_FREEZE_PLAN,CONFIRM_IMPORT_EXTERNAL,CONFIRM_REVIEW,CONFIRM_INTERNAL_SIM

def create_workspace_app399(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app398(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build399
    app.title='EagleEye Intelligence Platform – Build 399.0 Target Environment Soak & Recovery Qualification'; app.version='399.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def fp(req):
        m='|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')); return hashlib.sha256(m.encode()).hexdigest()
    def auth(req):
        i=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp(req),touch=True)
        if not i: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return i
    @app.get('/health')
    def health399():
        prev=dict(base_health() if callable(base_health) else {'ok':True}); q=ctx.target_soak_399.qualification_status(); prev.update({'build':'399.0','phase17_builds_completed':19,'target_environment_soak_framework':True,'required_soak_hours':72,'external_72h_soak_qualified':bool(q.get('external_72h_soak_qualified')),'production_release_ready':False}); return prev
    @app.get('/api/build399/phase17-status')
    def status(request:Request): auth(request); return ctx.build399.phase17_status()
    @app.post('/api/build399/soak/reference-plan')
    async def plan(request:Request):
        i=auth(request); b=await request.json(); p=ctx.target_soak_399.create_reference_plan()
        if b.get('freeze'): p=ctx.target_soak_399.freeze_plan(plan_id=p['plan_id'],identity=i,confirmation=str(b.get('confirmation') or ''))
        return p
    @app.post('/api/build399/soak/import-external')
    async def import_external(request:Request):
        i=auth(request); b=await request.json()
        try:return ctx.target_soak_399.import_external_bundle(plan_id=str(b.get('plan_id')),bundle=dict(b.get('bundle') or {}),identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/build399/soak/internal-framework-check')
    async def internal(request:Request):
        i=auth(request); b=await request.json()
        try:return ctx.target_soak_399.record_internal_framework_simulation(plan_id=str(b.get('plan_id')),identity=i,confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.post('/api/build399/soak/sessions/{session_id}/review')
    async def review(session_id:str,request:Request):
        i=auth(request); b=await request.json()
        try:return ctx.target_soak_399.review_external_session(session_id=session_id,identity=i,disposition=str(b.get('disposition') or ''),native_windows_verified=bool(b.get('native_windows_verified')),native_firefox_e2e_verified=bool(b.get('native_firefox_e2e_verified')),recovery_verified=bool(b.get('recovery_verified')),notes=str(b.get('notes') or ''),confirmation=str(b.get('confirmation') or ''))
        except (KeyError,ValueError,PermissionError) as e: raise HTTPException(400,str(e))
    @app.get('/api/build399/soak/status')
    def qstatus(request:Request): auth(request); return ctx.target_soak_399.qualification_status()
    @app.get('/api/build399/soak/sessions/{session_id}/verify')
    def verify(session_id:str,request:Request): auth(request); return ctx.target_soak_399.verify_session(session_id)
    return app
create_app=create_workspace_app399
