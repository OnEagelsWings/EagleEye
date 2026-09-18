from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from .app379 import COOKIE
from .app412 import create_workspace_app412

class PlanRequest(BaseModel):
    case_id:str; objective:str; subquestions:list[str]=Field(min_length=1,max_length=32); search_ids:list[str]=Field(default_factory=list,max_length=20); risk_constraints:list[str]|None=None; stop_conditions:list[str]|None=None

def create_workspace_app413(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app412(base_dir=base_dir); ctx=app.state.context; team=ctx.team_identity_359; _=ctx.build413
    app.title='EagleEye Intelligence Platform – Build 413.0 Investigation Planner'; app.version='413.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req:Request):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest(); identity=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity: raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return identity
    @app.get('/health')
    def health413():
        prev=dict(old() if callable(old) else {'ok':True}); s=ctx.build413.planner_status(); prev.update({'build':'413.0','phase':18,'phase18_builds_completed':13,'investigation_planner':True,'investigation_planner_gate_pass':s['investigation_planner_gate_pass'],'feedback_checked_before_build':True,'next_feedback_check':'before build 414','network_execution_on_boot':False,'production_release_ready':False}); return prev
    @app.get('/api/build413/planner/status')
    def status(request:Request): auth(request); return ctx.build413.planner_status()
    @app.post('/api/build413/plans')
    def create(body:PlanRequest,request:Request):
        identity=auth(request)
        try:return ctx.build413.create_investigation_plan(**body.model_dump(),identity=identity)
        except PermissionError as e: raise HTTPException(403,str(e))
        except (ValueError,KeyError) as e: raise HTTPException(400,str(e))
    @app.get('/api/build413/plans/{plan_id}')
    def get(plan_id:str,request:Request): auth(request); return ctx.build413.investigation_plan(plan_id)
    @app.get('/api/build413/cases/{case_id}/plans')
    def list_case(case_id:str,request:Request): auth(request); return ctx.build413.investigation_plans(case_id)
    return app
create_app=create_workspace_app413
