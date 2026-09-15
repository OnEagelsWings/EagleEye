from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app367 import COOKIE, create_workspace_app367


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop_route(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [route for route in app.router.routes if not (getattr(route, "path", None) == path and methods.intersection(set(getattr(route, "methods", set()) or set())))]


def create_workspace_app368(*, base_dir: str | Path | None = None) -> FastAPI:
    app=create_workspace_app367(base_dir=base_dir); ctx=app.state.context; team_identity=ctx.team_identity_359
    remote_enabled=bool(ctx.remote_team_364.config().get("enabled")); app.title="EagleEye Intelligence Platform – Build 368.0 Reference Intelligence"; app.version="368.0"
    base_health=next((r.endpoint for r in app.router.routes if getattr(r,"path",None)=="/health" and "GET" in set(getattr(r,"methods",set()) or set())),None)
    _drop_route(app,"/health",{"GET"}); _drop_route(app,"/api/cases/{case_id}/phase16/autonomous-cycle",{"POST"}); _drop_route(app,"/api/cases/{case_id}/phase16/opsec-protect",{"POST"})

    def fingerprint(request: Request)->str:
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")))
        return hashlib.sha256(material.encode("utf-8",errors="replace")).hexdigest()
    def require_auth(request: Request)->dict[str,Any]:
        token=request.cookies.get(COOKIE,""); fp=fingerprint(request); identity=team_identity.validate_session(token,client_fingerprint=fp,touch=True)
        if not identity and token and remote_enabled: ctx.build368.protect_remote_session(token=token,observed_fingerprint=fp,observed_ip=(request.client.host if request.client else ""))
        if not identity: raise HTTPException(status_code=401,detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity
    def require_case(request: Request,case_id: str,capability: str="case.read")->dict[str,Any]:
        identity=require_auth(request)
        try: ctx.build368.authorize(identity,case_id=case_id,capability=capability,object_type="reference_intelligence",object_id=case_id)
        except PermissionError as exc: raise HTTPException(status_code=403,detail=str(exc))
        return identity

    @app.get("/health")
    def health368():
        payload=dict(base_health() if callable(base_health) else {"ok":True}); payload.update({"build":"368.0","phase16_builds_completed":8,"reference_intelligence":True,"federal_register_exact_live_connector":True,"internet_archive_metadata_live_connector":True,"archive_content_download":False,"sanctions_live_connectors":False,"nara_live_connector":False,"govinfo_live_connector":False,"automatic_external_connections":False,"production_release_ready":False}); return payload

    @app.get("/api/build368/phase16-status")
    def phase16_status(request: Request): require_auth(request); return ctx.build368.phase16_status()
    @app.get("/api/build368/reference/connectors")
    def connector_catalog(request: Request): require_auth(request); return ctx.build368.reference_connector_catalog()
    @app.post("/api/cases/{case_id}/reference/prepare")
    async def prepare(case_id: str,request: Request):
        identity=require_case(request,case_id,"research.run"); body=await request.json()
        try: return ctx.build368.prepare_reference_source(case_id=case_id,connector_key=str(body.get("connector_key") or ""),identifier=str(body.get("identifier") or ""),identity=identity)
        except (ValueError,KeyError,PermissionError) as exc: raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))
    @app.post("/api/cases/{case_id}/reference/{source_id}/enqueue")
    async def enqueue(case_id: str,source_id: str,request: Request):
        identity=require_case(request,case_id,"crawler.run"); body=await request.json()
        try: return ctx.build368.enqueue_reference_live(case_id=case_id,source_id=source_id,identity=identity,confirmation=str(body.get("confirmation") or ""))
        except (ValueError,KeyError,PermissionError) as exc: raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))
    @app.get("/api/cases/{case_id}/reference/receipts")
    def receipts(case_id: str,request: Request,limit: int=100): require_case(request,case_id,"case.read"); return {"case_id":case_id,"receipts":ctx.build368.reference_receipts(case_id=case_id,limit=limit)}
    @app.get("/api/cases/{case_id}/reference/summary")
    def summary(case_id: str,request: Request): require_case(request,case_id,"case.read"); return ctx.build368.reference_case_summary(case_id=case_id)
    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id: str,request: Request): require_case(request,case_id,"research.run"); body=await request.json(); return ctx.build368.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))
    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str,request: Request): require_case(request,case_id,"research.run"); return ctx.build368.autonomous_opsec_protect(case_id=case_id)
    @app.get("/api/build368/final-status")
    def final_status(request: Request): require_auth(request); return ctx.build368.dashboard()

    @app.get("/cases/{case_id}/reference-intelligence")
    def console(case_id: str,request: Request):
        require_case(request,case_id,"case.read"); case=ctx.cases.get_case(case_id); summary=ctx.build368.reference_case_summary(case_id=case_id); status=ctx.build368.reference_status(); receipts=ctx.build368.reference_receipts(case_id=case_id,limit=50)
        rows="".join(f"<tr><td>{_esc(r['provider'])}</td><td><code>{_esc(r['identifier'])}</code></td><td>{_esc(r['crawl_status'])}</td><td>{'ja' if r['externally_validated'] else 'nein'}</td></tr>" for r in receipts) or "<tr><td colspan='4' class='muted'>Noch keine Reference-Receipts.</td></tr>"
        recs="".join(f"<tr><td>{_esc(x['connector_key'])}</td><td>{_esc(x['record'].get('title') or x['record'].get('identifier') or x['record'].get('document_number'))}</td></tr>" for x in summary['records'][:50]) or "<tr><td colspan='2' class='muted'>Noch keine Referenzdatensätze.</td></tr>"
        body=f"""<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Reference Intelligence · {_esc(case['title'])}</h1><p class='muted'>Legal/Government/Archive, evidence-first und reviewpflichtig.</p></div><div class='grid'><div class='card'><div class='metric'>{summary['receipt_count']}</div><div>Receipts</div></div><div class='card'><div class='metric'>{summary['externally_validated_receipts']}</div><div>extern validiert</div></div><div class='card'><div class='metric'>{len(summary['records'])}</div><div>Datensätze</div></div></div><div class='card'><h2>Grenzen</h2><p>Federal Register: {'extern validiert' if status['federal_register_externally_validated'] else 'nicht extern validiert'} · Internet Archive metadata: {'extern validiert' if status['internet_archive_externally_validated'] else 'nicht extern validiert'}.</p><p>OFAC/UN, NARA und GovInfo bleiben plan-only. Archive-Inhaltsdownload und fuzzy sanctions screening sind deaktiviert.</p></div><div class='card'><h2>Receipts</h2><table><tr><th>Provider</th><th>Identifier</th><th>Status</th><th>extern</th></tr>{rows}</table></div><div class='card'><h2>Referenzen</h2><table><tr><th>Connector</th><th>Referenz</th></tr>{recs}</table></div>"""
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Reference Intelligence</title><style>{css}</style></head><body><main>{body}</main></body></html>")
    return app
