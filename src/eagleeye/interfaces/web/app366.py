from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app365 import create_workspace_app365

COOKIE = "ee_auth_session"


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop_route(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [
        route for route in app.router.routes
        if not (getattr(route, "path", None) == path and methods.intersection(set(getattr(route, "methods", set()) or set())))
    ]


def create_workspace_app366(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app365(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 366.0 Corporate Live Data"
    app.version = "366.0"

    base_health = next((route.endpoint for route in app.router.routes if getattr(route, "path", None) == "/health" and "GET" in set(getattr(route, "methods", set()) or set())), None)
    _drop_route(app, "/health", {"GET"})
    _drop_route(app, "/api/cases/{case_id}/phase16/autonomous-cycle", {"POST"})
    _drop_route(app, "/api/cases/{case_id}/phase16/opsec-protect", {"POST"})

    def fingerprint(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()

    def require_auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, "")
        fp = fingerprint(request)
        identity = team_identity.validate_session(token, client_fingerprint=fp, touch=True)
        if not identity and token and remote_enabled:
            ctx.build366.protect_remote_session(token=token, observed_fingerprint=fp, observed_ip=(request.client.host if request.client else ""))
        if not identity:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def require_case(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        identity = require_auth(request)
        try:
            ctx.build366.authorize(identity, case_id=case_id, capability=capability, object_type="corporate_data", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return identity

    @app.get("/health")
    def health366():
        payload = dict(base_health() if callable(base_health) else {"ok": True})
        payload.update({
            "build": "366.0",
            "phase16_builds_completed": 6,
            "corporate_live_data": True,
            "gleif_live_connector": True,
            "sec_edgar_live_connector": True,
            "companies_house_live_connector": False,
            "explicit_live_confirmation_required": True,
            "automatic_external_connections": False,
            "production_release_ready": False,
        })
        return payload

    @app.get("/api/build366/phase16-status")
    def phase16_status(request: Request):
        require_auth(request)
        return ctx.build366.phase16_status()

    @app.get("/api/build366/corporate/connectors")
    def connector_catalog(request: Request):
        require_auth(request)
        return ctx.build366.connector_catalog()

    @app.post("/api/cases/{case_id}/corporate/prepare")
    async def corporate_prepare(case_id: str, request: Request):
        identity = require_case(request, case_id, "research.run")
        body = await request.json()
        try:
            return ctx.build366.prepare_corporate_source(case_id=case_id, connector_key=str(body.get("connector_key") or ""), identifier=str(body.get("identifier") or ""), identity=identity)
        except (ValueError, KeyError, PermissionError) as exc:
            raise HTTPException(status_code=400 if not isinstance(exc, PermissionError) else 403, detail=str(exc))

    @app.post("/api/cases/{case_id}/corporate/{source_id}/enqueue")
    async def corporate_enqueue(case_id: str, source_id: str, request: Request):
        identity = require_case(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build366.enqueue_corporate_live(case_id=case_id, source_id=source_id, identity=identity, confirmation=str(body.get("confirmation") or ""))
        except (ValueError, KeyError, PermissionError) as exc:
            raise HTTPException(status_code=400 if not isinstance(exc, PermissionError) else 403, detail=str(exc))

    @app.get("/api/cases/{case_id}/corporate/receipts")
    def corporate_receipts(case_id: str, request: Request, limit: int = 100):
        require_case(request, case_id, "case.read")
        return {"case_id": case_id, "receipts": ctx.build366.corporate_receipts(case_id=case_id, limit=limit)}

    @app.get("/api/cases/{case_id}/corporate/summary")
    def corporate_summary(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        return ctx.build366.corporate_case_summary(case_id=case_id)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def phase16_autonomous_cycle366(case_id: str, request: Request):
        require_case(request, case_id, "research.run")
        body = await request.json()
        return ctx.build366.run_autonomous_investigation(case_id=case_id, max_ticks=int(body.get("max_ticks", 8)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def phase16_opsec_protect366(case_id: str, request: Request):
        require_case(request, case_id, "research.run")
        return ctx.build366.autonomous_opsec_protect(case_id=case_id)

    @app.get("/api/build366/final-status")
    def build366_final_status(request: Request):
        require_auth(request)
        return ctx.build366.dashboard()

    @app.get("/cases/{case_id}/corporate")
    def corporate_console(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        case = ctx.cases.get_case(case_id)
        summary = ctx.build366.corporate_case_summary(case_id=case_id)
        status = ctx.build366.corporate_status()
        receipts = ctx.build366.corporate_receipts(case_id=case_id, limit=50)
        rows = "".join(
            f"<tr><td>{_esc(r['provider'])}</td><td><code>{_esc(r['identifier'])}</code></td><td>{_esc(r['crawl_status'])}</td><td>{'ja' if r['externally_validated'] else 'nein'}</td><td><code>{_esc(r['receipt_sha256'][:16])}…</code></td></tr>"
            for r in receipts
        ) or "<tr><td colspan='5' class='muted'>Noch keine Corporate-Receipts in diesem Fall.</td></tr>"
        records = "".join(
            f"<tr><td>{_esc(x['connector_key'])}</td><td>{_esc((x['record'].get('legal_name') or x['record'].get('name') or x['record'].get('company_name') or ''))}</td><td><code>{_esc(x['record'].get('lei') or x['record'].get('cik') or x['record'].get('company_number') or '')}</code></td></tr>"
            for x in summary["records"][:50]
        ) or "<tr><td colspan='3' class='muted'>Keine normalisierten Organisationsdatensätze.</td></tr>"
        body = f"""
        <p><a href='/cases/{_esc(case_id)}'>← Fall</a></p>
        <div class='card'><h1>Corporate Live Data · {_esc(case['title'])}</h1><p class='muted'>Öffentliche Organisationsdaten, review-first und fallbezogen. Live-Ausführung erfolgt nicht automatisch im Webserver.</p></div>
        <div class='grid'>
          <div class='card'><div class='metric'>{summary['receipt_count']}</div><div>Receipts</div></div>
          <div class='card'><div class='metric'>{summary['externally_validated_receipts']}</div><div>extern validiert</div></div>
          <div class='card'><div class='metric'>{len(summary['records'])}</div><div>AI-sichere Organisationsdatensätze</div></div>
          <div class='card'><div class='metric'>{len(summary['correlation_candidates'])}</div><div>Review-Leads</div></div>
        </div>
        <div class='card'><h2>Connector-Status</h2><p>GLEIF extern validiert: <strong>{'ja' if status['gleif_externally_validated'] else 'nein'}</strong> · SEC EDGAR extern validiert: <strong>{'ja' if status['sec_externally_validated'] else 'nein'}</strong></p><p>Companies House bleibt plan-only/auth-required. Keine automatischen externen Verbindungen.</p></div>
        <div class='card'><h2>Corporate Receipts</h2><table><tr><th>Provider</th><th>Identifier</th><th>Status</th><th>extern</th><th>Receipt</th></tr>{rows}</table></div>
        <div class='card'><h2>Normalisierte Organisationsdaten</h2><table><tr><th>Connector</th><th>Name</th><th>Identifier</th></tr>{records}</table><p class='muted'>Adress-/EIN-Felder bleiben im Evidence-Artefakt, werden aber nicht routinemäßig in den AI-Kontext übernommen.</p></div>
        <div class='card'><h2>API</h2><p><a href='/api/cases/{_esc(case_id)}/corporate/summary'>Summary JSON</a> · <a href='/api/cases/{_esc(case_id)}/corporate/receipts'>Receipts JSON</a></p></div>
        """
        css = "body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Corporate Data · {_esc(case['title'])}</title><style>{css}</style></head><body><main>{body}</main></body></html>")

    return app
