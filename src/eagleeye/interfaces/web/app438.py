from __future__ import annotations
from fastapi import HTTPException,Request
from .app379 import COOKIE
from .app437 import create_workspace_app437

def create_workspace_app438(*,base_dir=None):
    app=create_workspace_app437(base_dir=base_dir);ctx=app.state.context;team=ctx.team_identity_359;_=ctx.build438;app.title='EagleEye Build 438.0';app.version='438.0'
    old=next((r.endpoint for r in app.router.routes if getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set())),None)
    app.router.routes[:]=[r for r in app.router.routes if not(getattr(r,'path',None)=='/health' and 'GET' in set(getattr(r,'methods',set()) or set()))]
    def auth(req):
        import hashlib
        fp=hashlib.sha256('|'.join((req.headers.get('user-agent',''),req.headers.get('accept-language',''),req.client.host if req.client else '')).encode()).hexdigest();x=team.validate_session(req.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not x:raise HTTPException(401,'Anmeldung erforderlich oder Sitzung abgelaufen')
        return x
    def case_auth(req,case_id,capability='case.read'):
        identity=auth(req)
        try:ctx.team_governance_359.authorize(identity,case_id=str(case_id),capability=capability,object_type='phase19',object_id=str(case_id))
        except PermissionError as e:raise HTTPException(403,str(e))
        return identity
    def same_origin(req):
        site=str(req.headers.get('sec-fetch-site') or '').strip().lower()
        if site and site not in {'same-origin','none'}:raise HTTPException(403,'Cross-origin mutation blocked')
        origin=str(req.headers.get('origin') or '').strip().rstrip('/')
        if origin:
            expected=(str(req.url.scheme)+'://'+str(req.headers.get('host') or '')).rstrip('/')
            if origin!=expected:raise HTTPException(403,'Cross-origin mutation blocked')
    @app.get('/health')
    def health():
        h=dict(old() if callable(old) else {'ok':True});s=ctx.build438.temporal_relationship_status_438()
        h.update({'build':'438.0','phase':19,'phase19_builds_completed':18,'temporal_relationship_fusion':True,'reviewed_identity_fusion_only':True,'provenance_preserved':True,'explicit_source_relationships_only':True,'causality_inferred':False,'production_release_ready':False,'integrity_valid':s['integrity_valid']});return h
    @app.get('/api/build438/fusion/status')
    def status438(request:Request):auth(request);return ctx.build438.temporal_relationship_status_438()
    @app.get('/api/build438/cases/{case_id}/fusion/report')
    def report438(case_id:str,request:Request,include_fixtures:bool=False):case_auth(request,case_id,'case.read');return ctx.build438.temporal_relationship_report_438(case_id,include_fixtures)
    @app.get('/api/build438/cases/{case_id}/fusion/groups')
    def groups438(case_id:str,request:Request):case_auth(request,case_id,'case.read');return ctx.build438.fusion_groups_438(case_id)
    @app.get('/api/build438/cases/{case_id}/fusion/timeline')
    def timeline438(case_id:str,request:Request,include_fixtures:bool=False):case_auth(request,case_id,'case.read');return ctx.build438.fused_timeline_438(case_id,include_fixtures)
    @app.get('/api/build438/cases/{case_id}/fusion/relationships')
    def relationships438(case_id:str,request:Request,include_fixtures:bool=False):case_auth(request,case_id,'case.read');return ctx.build438.fused_relationship_graph_438(case_id,include_fixtures)
    @app.get('/api/build438/cases/{case_id}/fusion/entities/{entity_id}')
    def entity438(case_id:str,entity_id:str,request:Request,include_fixtures:bool=False):
        case_auth(request,case_id,'case.read')
        try:return ctx.build438.fused_entity_context_438(case_id,entity_id,include_fixtures)
        except KeyError as e:raise HTTPException(404,str(e))
    @app.post('/api/build438/cases/{case_id}/fusion/run')
    async def run438(case_id:str,request:Request):
        same_origin(request);identity=case_auth(request,case_id,'research.run')
        try:
            b=await request.json()
            if not isinstance(b,dict):b={}
            return ctx.build438.fuse_temporal_relationship_case(identity=identity,case_id=case_id,include_fixtures=bool(b.get('include_fixtures',False)))
        except PermissionError as e:raise HTTPException(403,str(e))
        except RuntimeError as e:raise HTTPException(409,str(e))
        except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
    @app.post('/api/build438/cases/{case_id}/fusion/selftest')
    def selftest438(case_id:str,request:Request):
        same_origin(request);identity=case_auth(request,case_id,'research.run')
        try:return ctx.build438.run_temporal_relationship_case_selftest(identity=identity,case_id=case_id)
        except PermissionError as e:raise HTTPException(403,str(e))
        except RuntimeError as e:raise HTTPException(409,str(e))
        except (ValueError,KeyError,TypeError) as e:raise HTTPException(400,str(e))
    return app
create_app=create_workspace_app438
