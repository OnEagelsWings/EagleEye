from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app366 import COOKIE, create_workspace_app366


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop_route(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [route for route in app.router.routes if not (getattr(route, "path", None) == path and methods.intersection(set(getattr(route, "methods", set()) or set())))]


def create_workspace_app367(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app366(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 367.0 Procurement / Public Money"
    app.version = "367.0"

    base_health = next((route.endpoint for route in app.router.routes if getattr(route, "path", None) == "/health" and "GET" in set(getattr(route, "methods", set()) or set())), None)
    _drop_route(app, "/health", {"GET"})
    _drop_route(app, "/api/cases/{case_id}/phase16/autonomous-cycle", {"POST"})
    _drop_route(app, "/api/cases/{case_id}/phase16/opsec-protect", {"POST"})

    def fingerprint(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()

    def require_auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, ""); fp = fingerprint(request)
        identity = team_identity.validate_session(token, client_fingerprint=fp, touch=True)
        if not identity and token and remote_enabled:
            ctx.build367.protect_remote_session(token=token, observed_fingerprint=fp, observed_ip=(request.client.host if request.client else ""))
        if not identity: raise HTTPException(status_code=401, detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def require_case(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        identity = require_auth(request)
        try: ctx.build367.authorize(identity, case_id=case_id, capability=capability, object_type="public_money", object_id=case_id)
        except PermissionError as exc: raise HTTPException(status_code=403, detail=str(exc))
        return identity

    @app.get("/health")
    def health367():
        payload = dict(base_health() if callable(base_health) else {"ok": True})
        payload.update({"build":"367.0","phase16_builds_completed":7,"procurement_public_money":True,"usaspending_award_live_connector":True,"ted_notice_xml_live_connector":True,"ted_search_live_connector":False,"explicit_live_confirmation_required":True,"automatic_external_connections":False,"production_release_ready":False})
        return payload

    @app.get("/api/build367/phase16-status")
    def phase16_status(request: Request):
        require_auth(request); return ctx.build367.phase16_status()

    @app.get("/api/build367/public-money/connectors")
    def connector_catalog(request: Request):
        require_auth(request); return ctx.build367.public_money_connector_catalog()

    @app.post("/api/cases/{case_id}/public-money/prepare")
    async def public_money_prepare(case_id: str, request: Request):
        identity=require_case(request,case_id,"research.run"); body=await request.json()
        try: return ctx.build367.prepare_public_money_source(case_id=case_id,connector_key=str(body.get("connector_key") or ""),identifier=str(body.get("identifier") or ""),identity=identity)
        except (ValueError,KeyError,PermissionError) as exc: raise HTTPException(status_code=400 if not isinstance(exc,PermissionError) else 403,detail=str(exc))

    @app.post("/api/cases/{case_id}/public-money/{source_id}/enqueue")
    async def public_money_enqueue(case_id: str, source_id: str, request: Request):
        identity=require_case(request,case_id,"crawler.run"); body=await request.json()
        try: return ctx.build367.enqueue_public_money_live(case_id=case_id,source_id=source_id,identity=identity,confirmation=str(body.get("confirmation") or ""))
        except (ValueError,KeyError,PermissionError) as exc: raise HTTPException(status_code=400 if not isinstance(exc,PermissionError) else 403,detail=str(exc))

    @app.get("/api/cases/{case_id}/public-money/receipts")
    def public_money_receipts(case_id: str, request: Request, limit: int = 100):
        require_case(request,case_id,"case.read"); return {"case_id":case_id,"receipts":ctx.build367.public_money_receipts(case_id=case_id,limit=limit)}

    @app.get("/api/cases/{case_id}/public-money/summary")
    def public_money_summary(case_id: str, request: Request):
        require_case(request,case_id,"case.read"); return ctx.build367.public_money_case_summary(case_id=case_id)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def phase16_autonomous_cycle367(case_id: str, request: Request):
        require_case(request,case_id,"research.run"); body=await request.json(); return ctx.build367.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def phase16_opsec_protect367(case_id: str, request: Request):
        require_case(request,case_id,"research.run"); return ctx.build367.autonomous_opsec_protect(case_id=case_id)

    @app.get("/api/build367/final-status")
    def build367_final_status(request: Request):
        require_auth(request); return ctx.build367.dashboard()

    @app.get("/cases/{case_id}/public-money")
    def public_money_console(case_id: str, request: Request):
        require_case(request,case_id,"case.read"); case=ctx.cases.get_case(case_id); summary=ctx.build367.public_money_case_summary(case_id=case_id); status=ctx.build367.public_money_status(); receipts=ctx.build367.public_money_receipts(case_id=case_id,limit=50)
        receipt_rows="".join(f"<tr><td>{_esc(r['provider'])}</td><td><code>{_esc(r['identifier'])}</code></td><td>{_esc(r['crawl_status'])}</td><td>{'ja' if r['externally_validated'] else 'nein'}</td><td><code>{_esc(r['receipt_sha256'][:16])}…</code></td></tr>" for r in receipts) or "<tr><td colspan='5' class='muted'>Noch keine Public-Money-Receipts.</td></tr>"
        flow_rows="".join(f"<tr><td>{_esc(x.get('flow_type'))}</td><td>{_esc(x.get('from'))}</td><td>{_esc(x.get('to') or ', '.join(x.get('to_candidates') or []))}</td><td>{_esc(x.get('amount') or ', '.join(map(str,x.get('amount_candidates') or [])))}</td></tr>" for x in summary["money_flow_candidates"][:50]) or "<tr><td colspan='4' class='muted'>Noch keine Geldfluss-/Vergabe-Leads.</td></tr>"
        body=f"""
        <p><a href='/cases/{_esc(case_id)}'>← Fall</a></p>
        <div class='card'><h1>Procurement / Public Money · {_esc(case['title'])}</h1><p class='muted'>Öffentliche Vergabe- und Ausgabendaten, evidence-first, reviewpflichtig und fallbezogen.</p></div>
        <div class='grid'><div class='card'><div class='metric'>{summary['receipt_count']}</div><div>Receipts</div></div><div class='card'><div class='metric'>{summary['externally_validated_receipts']}</div><div>extern validiert</div></div><div class='card'><div class='metric'>{len(summary['money_flow_candidates'])}</div><div>Geldfluss-/Vergabe-Leads</div></div><div class='card'><div class='metric'>{len(summary['corporate_link_candidates'])}</div><div>Corporate-Link-Leads</div></div></div>
        <div class='card'><h2>Connector-Status</h2><p>USAspending extern validiert: <strong>{'ja' if status['usaspending_externally_validated'] else 'nein'}</strong> · TED Notice XML extern validiert: <strong>{'ja' if status['ted_externally_validated'] else 'nein'}</strong></p><p>TED Search API bleibt plan-only, weil der qualifizierte Crawler keine POST-Suche ausführt.</p></div>
        <div class='card'><h2>Receipts</h2><table><tr><th>Provider</th><th>Identifier</th><th>Status</th><th>extern</th><th>Receipt</th></tr>{receipt_rows}</table></div>
        <div class='card'><h2>Geldfluss-/Vergabe-Leads</h2><table><tr><th>Typ</th><th>Von</th><th>An</th><th>Betrag</th></tr>{flow_rows}</table><p class='muted'>Leads sind keine bestätigten Identitäts- oder Zahlungsbeziehungen und benötigen menschliche Prüfung.</p></div>
        <div class='card'><h2>API</h2><p><a href='/api/cases/{_esc(case_id)}/public-money/summary'>Summary JSON</a> · <a href='/api/cases/{_esc(case_id)}/public-money/receipts'>Receipts JSON</a></p></div>
        """
        css="body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Public Money · {_esc(case['title'])}</title><style>{css}</style></head><body><main>{body}</main></body></html>")

    return app
