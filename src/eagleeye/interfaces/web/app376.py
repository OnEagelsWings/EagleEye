from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from .app375 import COOKIE, create_workspace_app375

def _drop(app:FastAPI,path:str,methods:set[str])->None:
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)==path and methods.intersection(set(getattr(r,'methods',set()) or set())))]

def create_workspace_app376(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app375(base_dir=base_dir);ctx=app.state.context;team_identity=ctx.team_identity_359;remote_enabled=bool(ctx.remote_team_364.config().get('enabled'));app.title='EagleEye Intelligence Platform – Build 376.0 Dossier vNext';app.version='376.0'
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    for path,methods in [("/health",{"GET"}),("/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}),("/api/cases/{case_id}/phase16/opsec-protect",{"POST"})]:_drop(app,path,methods)
    def fp(request:Request)->str:
        material='|'.join((request.headers.get('user-agent',''),request.headers.get('accept-language',''),(request.client.host if request.client else '')));return hashlib.sha256(material.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,'');fingerprint=fp(request);ident=team_identity.validate_session(token,client_fingerprint=fingerprint,touch=True)
        if not ident and token and remote_enabled:ctx.build376.protect_remote_session(token=token,observed_fingerprint=fingerprint,observed_ip=(request.client.host if request.client else ''))
        if not ident:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return ident
    def caseauth(request:Request,case_id:str,capability:str='case.read')->dict[str,Any]:
        ident=auth(request)
        try:ctx.build376.authorize(ident,case_id=case_id,capability=capability,object_type='dossier_vnext_v376',object_id=case_id)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        return ident
    @app.get('/health')
    def health376():
        p=dict(base_health() if callable(base_health) else {'ok':True});p.update({'build':'376.0','phase16_builds_completed':16,'dossier_vnext':True,'source_coverage':True,'negative_evidence_semantics':True,'staleness_register':True,'crawler_improvement_build':376,'automatic_gap_crawl':False,'production_release_ready':False});return p
    @app.get('/api/build376/phase16-status')
    def phase(request:Request):auth(request);return ctx.build376.phase16_status()
    @app.get('/api/build376/final-status')
    def final(request:Request):auth(request);return ctx.build376.dashboard()
    @app.get('/api/cases/{case_id}/dossier376/coverage')
    def coverage(case_id:str,request:Request):ident=caseauth(request,case_id,'crawler.monitor');return ctx.build376.dossier_coverage(case_id=case_id,identity=ident)
    @app.get('/api/cases/{case_id}/dossier376/packet')
    def packet(case_id:str,request:Request):ident=caseauth(request,case_id,'crawler.monitor');return ctx.build376.dossier_packet(case_id=case_id,identity=ident)
    @app.post('/api/cases/{case_id}/dossier376/absence-observation')
    async def absence(case_id:str,request:Request):
        ident=caseauth(request,case_id,'crawler.monitor');body=await request.json()
        try:return ctx.build376.record_absence_observation(case_id=case_id,source_id=str(body.get('source_id') or ''),crawl_run_id=str(body.get('crawl_run_id') or ''),query_scope=str(body.get('query_scope') or ''),observation=str(body.get('observation') or ''),identity=ident,confirmation=str(body.get('confirmation') or ''))
        except (PermissionError,ValueError,KeyError) as exc:raise HTTPException(403 if isinstance(exc,PermissionError) else 400,str(exc))
    @app.get('/api/cases/{case_id}/dossier376/build')
    def dossier(case_id:str,request:Request):caseauth(request,case_id,'case.read');return ctx.build376.build_dossier_vnext(case_id=case_id,refresh_hypotheses=False)
    @app.post('/api/cases/{case_id}/phase16/autonomous-cycle')
    async def autonomous(case_id:str,request:Request):caseauth(request,case_id,'case.read');body=await request.json();return ctx.build376.run_autonomous_investigation(case_id=case_id,max_ticks=max(1,min(int(body.get('max_ticks',8)),20)))
    @app.post('/api/cases/{case_id}/phase16/opsec-protect')
    async def opsec(case_id:str,request:Request):caseauth(request,case_id,'case.manage');return ctx.build376.autonomous_opsec_protect(case_id=case_id)
    return app
