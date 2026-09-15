from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app364 import create_workspace_app364

COOKIE = "ee_auth_session"


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop_route(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [
        route for route in app.router.routes
        if not (getattr(route, "path", None) == path and methods.intersection(set(getattr(route, "methods", set()) or set())))
    ]


def create_workspace_app365(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app364(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 365.0 Operations"
    app.version = "365.0"

    base_health = next((route.endpoint for route in app.router.routes if getattr(route, "path", None) == "/health" and "GET" in set(getattr(route, "methods", set()) or set())), None)
    _drop_route(app, "/health", {"GET"})

    # Replace only the two Phase-16 execution routes so all existing UI remains
    # compatible while Build 365's AI/OPSEC operational safeguards become active.
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
            ctx.build365.protect_remote_session(token=token, observed_fingerprint=fp, observed_ip=(request.client.host if request.client else ""))
        if not identity:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def require_case(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        identity = require_auth(request)
        try:
            ctx.build365.authorize(identity, case_id=case_id, capability=capability, object_type="operations", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
        return identity

    @app.get("/health")
    def health365():
        payload = dict(base_health() if callable(base_health) else {"ok": True, "build": "365.0"})
        payload.update({
            "build": "365.0",
            "phase16_builds_completed": 5,
            "operations_console": True,
            "case_scoped_metrics": True,
            "worker_queue_health": True,
            "case_scoped_trace": True,
            "incident_console": True,
            "opsec_operational_circuit_breaker": True,
            "external_operations_validation": "not_run",
            "production_release_ready": False,
        })
        return payload

    @app.get("/api/build365/phase16-status")
    def phase16_status(request: Request):
        require_auth(request)
        return ctx.build365.phase16_status()

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def phase16_autonomous_cycle365(case_id: str, request: Request):
        require_case(request, case_id, "research.run")
        body = await request.json()
        return ctx.build365.run_autonomous_investigation(case_id=case_id, max_ticks=int(body.get("max_ticks", 8)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def phase16_opsec_protect365(case_id: str, request: Request):
        require_case(request, case_id, "research.run")
        return ctx.build365.autonomous_opsec_protect(case_id=case_id)

    @app.get("/api/cases/{case_id}/operations/metrics")
    def operations_metrics(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        return ctx.build365.operations_metrics(case_id=case_id)

    @app.get("/api/cases/{case_id}/operations/workers")
    def operations_workers(case_id: str, request: Request):
        require_case(request, case_id, "crawler.monitor")
        return ctx.build365.operations_worker_health(case_id=case_id)

    @app.get("/api/cases/{case_id}/operations/trace")
    def operations_trace(case_id: str, request: Request, limit: int = 200):
        require_case(request, case_id, "case.read")
        return ctx.build365.operations_trace(case_id=case_id, limit=limit)

    @app.get("/api/cases/{case_id}/operations/incidents")
    def operations_incidents(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        return ctx.build365.operations_incidents(case_id=case_id)

    @app.get("/api/cases/{case_id}/operations/readiness")
    def operations_readiness(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        return ctx.build365.operations_readiness(case_id=case_id)

    @app.get("/api/build365/final-status")
    def build365_final_status(request: Request):
        require_auth(request)
        return ctx.build365.dashboard()

    @app.get("/cases/{case_id}/operations")
    def operations_console(case_id: str, request: Request):
        require_case(request, case_id, "case.read")
        case = ctx.cases.get_case(case_id)
        m = ctx.build365.operations_metrics(case_id=case_id)
        w = ctx.build365.operations_worker_health(case_id=case_id)
        i = ctx.build365.operations_incidents(case_id=case_id)
        r = ctx.build365.operations_readiness(case_id=case_id)
        rows = "".join(
            f"<tr><td>{_esc(x['severity'])}</td><td>{_esc(x['category'])}</td><td>{_esc(x['event_type'])}</td><td>{_esc(x['state'])}</td><td><code>{_esc(x['source_id'])}</code></td></tr>"
            for x in i["incidents"][:50]
        ) or "<tr><td colspan='5' class='muted'>Keine operativen Incidents.</td></tr>"
        workers = "".join(
            f"<tr><td>{_esc(x['worker_id'])}</td><td>{x['active_jobs']}</td><td>{_esc(x['state'])}</td><td>{_esc(x['earliest_lease'])}</td></tr>"
            for x in w["workers"]
        ) or "<tr><td colspan='4' class='muted'>Keine aktiven Worker-Leases.</td></tr>"
        counts = m["job_counts"]
        body = f"""
        <p><a href='/cases/{_esc(case_id)}'>← Fall</a></p>
        <div class='card'><h1>Operations · {_esc(case['title'])}</h1><p class='muted'>Fallbezogene Laufzeit-, Queue-, Crawler- und Sicherheitslage. Kein Cross-Case-Aggregat.</p></div>
        <div class='grid'>
          <div class='card'><div class='metric'>{r['local_operational_readiness_score']}</div><div>Local Ops Readiness</div></div>
          <div class='card'><div class='metric'>{sum(counts.values())}</div><div>Jobs gesamt</div></div>
          <div class='card'><div class='metric'>{w['expired_worker_leases']}</div><div>Expired Leases</div></div>
          <div class='card'><div class='metric'>{i['count']}</div><div>Incidents</div></div>
          <div class='card'><div class='metric'>{m['fetches']['count']}</div><div>Crawler Fetches</div></div>
          <div class='card'><div class='metric'>{m['evidence_objects']}</div><div>Evidence Objects</div></div>
        </div>
        <div class='card'><h2>Readiness</h2><p class='{"ok" if r['local_operational_ready'] else "blocked"}'>{'LOCAL READY' if r['local_operational_ready'] else 'ATTENTION REQUIRED'}</p><p class='muted'>{_esc(r['truthful_note'])}</p><p>Production release ready: <strong>Nein</strong> · External operations validation: <strong>{_esc(r['external_operations_validation'])}</strong></p></div>
        <div class='card'><h2>Worker Health</h2><table><tr><th>Worker</th><th>aktive Jobs</th><th>Status</th><th>früheste Lease</th></tr>{workers}</table></div>
        <div class='card'><h2>Incident Console</h2><table><tr><th>Severity</th><th>Kategorie</th><th>Ereignis</th><th>Status</th><th>Quelle</th></tr>{rows}</table></div>
        <div class='card'><h2>API / Trace</h2><p><a href='/api/cases/{_esc(case_id)}/operations/trace'>Fall-Trace (JSON)</a> · <a href='/api/cases/{_esc(case_id)}/operations/metrics'>Metriken (JSON)</a></p></div>
        """
        css = "body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}.ok{color:#166534}.blocked{color:#991b1b}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Operations · {_esc(case['title'])}</title><style>{css}</style></head><body><main>{body}</main></body></html>")

    return app
