from __future__ import annotations
import hashlib, html
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from .app371 import COOKIE, create_workspace_app371

def _esc(v:Any)->str:return html.escape(str(v if v is not None else ""))
def _drop(app:FastAPI,path:str,methods:set[str])->None:app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,"path",None)==path and methods.intersection(set(getattr(r,"methods",set()) or set())))]

def create_workspace_app372(*,base_dir:str|Path|None=None)->FastAPI:
    app=create_workspace_app371(base_dir=base_dir);ctx=app.state.context;team_identity=ctx.team_identity_359;remote_enabled=bool(ctx.remote_team_364.config().get("enabled"));app.title="EagleEye Intelligence Platform – Build 372.0 Entity Resolution Evaluation";app.version="372.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    for path,methods in [("/health",{"GET"}),("/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}),("/api/cases/{case_id}/phase16/opsec-protect",{"POST"})]:_drop(app,path,methods)
    def fp(request:Request)->str:
        m="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")));return hashlib.sha256(m.encode()).hexdigest()
    def auth(request:Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,"");f=fp(request);ident=team_identity.validate_session(token,client_fingerprint=f,touch=True)
        if not ident and token and remote_enabled:ctx.build372.protect_remote_session(token=token,observed_fingerprint=f,observed_ip=(request.client.host if request.client else ""))
        if not ident:raise HTTPException(401,"Anmeldung erforderlich oder Sitzung abgelaufen")
        return ident
    def caseauth(request:Request,case_id:str,capability:str="case.read")->dict[str,Any]:
        ident=auth(request)
        try:ctx.build372.authorize(ident,case_id=case_id,capability=capability,object_type="entity_resolution_eval",object_id=case_id)
        except PermissionError as exc:raise HTTPException(403,str(exc))
        return ident
    @app.get("/health")
    def health372():
        p=dict(base_health() if callable(base_health) else {"ok":True});p.update({"build":"372.0","phase16_builds_completed":12,"entity_resolution_evaluation":True,"crawler_improvement_build":372,"false_link_calibration":True,"source_quality_calibration":True,"continuous_crawler_expansion_370_380":True,"automatic_identity_merge":False,"production_release_ready":False});return p
    @app.get("/api/build372/phase16-status")
    def phase(request:Request):auth(request);return ctx.build372.phase16_status()
    @app.get("/api/build372/final-status")
    def final(request:Request):auth(request);return ctx.build372.dashboard()
    @app.get("/api/cases/{case_id}/entity372/source-quality")
    def source_quality_case(case_id:str,request:Request):caseauth(request,case_id);return ctx.build372.crawler_source_quality_case(case_id=case_id)
    @app.get("/api/cases/{case_id}/entity372/lead-quality/{job_id}")
    def lead_quality(case_id:str,job_id:str,request:Request):
        caseauth(request,case_id)
        try:
            out=ctx.build372.crawler_lead_quality(job_id=job_id)
            if out.get("case_id")!=case_id:raise PermissionError("cross-case lead quality prohibited")
            return out
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc))
    @app.post("/api/cases/{case_id}/entity372/evaluate")
    async def evaluate(case_id:str,request:Request):
        ident=caseauth(request,case_id,"research.run");body=await request.json()
        try:return ctx.build372.evaluate_labeled_entity_comparisons(case_id=case_id,labeled=list(body.get("labeled") or []),identity=ident,evaluation_name=str(body.get("evaluation_name") or "analyst_holdout"))
        except PermissionError as exc:raise HTTPException(403,str(exc))
        except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc))
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id:str,request:Request):caseauth(request,case_id,"research.run");body=await request.json();return ctx.build372.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id:str,request:Request):caseauth(request,case_id,"research.run");return ctx.build372.autonomous_opsec_protect(case_id=case_id)
    @app.get("/cases/{case_id}/entity-resolution-eval")
    def console(case_id:str,request:Request):
        caseauth(request,case_id);case=ctx.cases.get_case(case_id);er=ctx.build372.entity_case_status(case_id=case_id);sq=ctx.build372.crawler_source_quality_case(case_id=case_id)
        body=f"""<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Entity Resolution Eval · {_esc(case['title'])}</h1><p>False-link calibration, source-quality annotation and holdout evaluation. Scores remain review aids, not identity probabilities.</p></div><div class='grid'><div class='card'><div class='metric'>{er['unresolved_review_items']}</div><div>Review items</div></div><div class='card'><div class='metric'>{sq['lead_count']}</div><div>Calibrated crawler leads</div></div><div class='card'><div class='metric'>{sq['quality_bands'].get('high',0)}</div><div>High-quality source leads</div></div></div><div class='card'><h2>Evaluation boundaries</h2><ul><li>Holdout labels never change thresholds automatically.</li><li>Source quality cannot confirm identity or skip review.</li><li>False-link metrics are separated from probability claims.</li><li>No automatic merge.</li></ul></div>"""
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1100px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}a{color:#1d4ed8;text-decoration:none}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Entity Resolution Eval</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
