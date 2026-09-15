from __future__ import annotations

import hashlib
import html
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .app372 import COOKIE, create_workspace_app372


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _drop(app: FastAPI, path: str, methods: set[str]) -> None:
    app.router.routes[:] = [
        r for r in app.router.routes
        if not (getattr(r, "path", None) == path and methods.intersection(set(getattr(r, "methods", set()) or set())))
    ]


def create_workspace_app373(*, base_dir: str | Path | None = None) -> FastAPI:
    app = create_workspace_app372(base_dir=base_dir)
    ctx = app.state.context
    team_identity = ctx.team_identity_359
    remote_enabled = bool(ctx.remote_team_364.config().get("enabled"))
    app.title = "EagleEye Intelligence Platform – Build 373.0 Analyst Graph UX"
    app.version = "373.0"

    base_health = next(
        (r.endpoint for r in app.router.routes if getattr(r, "path", None) == "/health" and "GET" in set(getattr(r, "methods", set()) or set())),
        None,
    )
    for path, methods in [
        ("/health", {"GET"}),
        ("/api/cases/{case_id}/phase16/autonomous-cycle", {"POST"}),
        ("/api/cases/{case_id}/phase16/opsec-protect", {"POST"}),
    ]:
        _drop(app, path, methods)

    def fp(request: Request) -> str:
        material = "|".join((request.headers.get("user-agent", ""), request.headers.get("accept-language", ""), (request.client.host if request.client else "")))
        return hashlib.sha256(material.encode()).hexdigest()

    def auth(request: Request) -> dict[str, Any]:
        token = request.cookies.get(COOKIE, "")
        fingerprint = fp(request)
        identity = team_identity.validate_session(token, client_fingerprint=fingerprint, touch=True)
        if not identity and token and remote_enabled:
            ctx.build373.protect_remote_session(token=token, observed_fingerprint=fingerprint, observed_ip=(request.client.host if request.client else ""))
        if not identity:
            raise HTTPException(401, "Anmeldung erforderlich oder Sitzung abgelaufen")
        return identity

    def caseauth(request: Request, case_id: str, capability: str = "case.read") -> dict[str, Any]:
        identity = auth(request)
        try:
            ctx.build373.authorize(identity, case_id=case_id, capability=capability, object_type="analyst_graph_v373", object_id=case_id)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        return identity

    @app.get("/health")
    def health373():
        payload = dict(base_health() if callable(base_health) else {"ok": True})
        payload.update({
            "build": "373.0",
            "phase16_builds_completed": 13,
            "analyst_graph_ux": True,
            "crawler_improvement_build": 373,
            "graph_aware_navigation": True,
            "analyst_selected_sources_only": True,
            "automatic_graph_scope_expansion": False,
            "automatic_identity_merge": False,
            "continuous_crawler_expansion_370_380": True,
            "production_release_ready": False,
        })
        return payload

    @app.get("/api/build373/phase16-status")
    def phase(request: Request):
        auth(request)
        return ctx.build373.phase16_status()

    @app.get("/api/build373/final-status")
    def final(request: Request):
        auth(request)
        return ctx.build373.dashboard()

    @app.get("/api/cases/{case_id}/graph373")
    def graph(case_id: str, request: Request, max_nodes: int = 180, max_edges: int = 360):
        identity = caseauth(request, case_id)
        try:
            return ctx.build373.analyst_graph(case_id=case_id, identity=identity, max_nodes=max_nodes, max_edges=max_edges)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))

    @app.get("/api/cases/{case_id}/graph373/focus")
    def focus(case_id: str, node_id: str, request: Request, depth: int = 1, max_nodes: int = 60):
        identity = caseauth(request, case_id)
        try:
            return ctx.build373.analyst_graph_focus(case_id=case_id, node_id=node_id, identity=identity, depth=depth, max_nodes=max_nodes)
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except KeyError as exc:
            raise HTTPException(404, str(exc))

    @app.post("/api/cases/{case_id}/graph373/navigation-plan")
    async def navigation_plan(case_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build373.graph_navigation_plan(
                case_id=case_id,
                root_entity_id=str(body.get("root_entity_id") or ""),
                source_ids=list(body.get("source_ids") or []),
                identity=identity,
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/cases/{case_id}/graph373/navigate")
    async def navigate(case_id: str, request: Request):
        identity = caseauth(request, case_id, "crawler.run")
        body = await request.json()
        try:
            return ctx.build373.graph_navigate(
                case_id=case_id,
                root_entity_id=str(body.get("root_entity_id") or ""),
                source_ids=list(body.get("source_ids") or []),
                identity=identity,
                confirmation=str(body.get("confirmation") or ""),
            )
        except PermissionError as exc:
            raise HTTPException(403, str(exc))
        except (ValueError, KeyError) as exc:
            raise HTTPException(400, str(exc))

    @app.get("/api/cases/{case_id}/graph373/navigation-status")
    def navigation_status(case_id: str, request: Request):
        caseauth(request, case_id)
        return ctx.build373.graph_navigation_status(case_id=case_id)

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def cycle(case_id: str, request: Request):
        caseauth(request, case_id, "research.run")
        body = await request.json()
        return ctx.build373.run_autonomous_investigation(case_id=case_id, max_ticks=int(body.get("max_ticks", 8)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def opsec(case_id: str, request: Request):
        caseauth(request, case_id, "research.run")
        return ctx.build373.autonomous_opsec_protect(case_id=case_id)

    @app.get("/cases/{case_id}/analyst-graph")
    def analyst_graph_page(case_id: str, request: Request):
        identity = caseauth(request, case_id)
        case = ctx.cases.get_case(case_id)
        graph = ctx.build373.analyst_graph(case_id=case_id, identity=identity, max_nodes=120, max_edges=240)
        nodes = graph["nodes"]
        edges = graph["edges"]
        node_rows = "".join(
            f"<tr data-kind='{_esc(n.get('kind'))}'><td><code>{_esc(n.get('id'))}</code></td><td>{_esc(n.get('kind'))}</td><td>{_esc(n.get('label'))}</td><td>{'yes' if n.get('review_required') else 'no'}</td></tr>"
            for n in nodes
        )
        edge_rows = "".join(
            f"<tr data-kind='{_esc(e.get('kind'))}'><td>{_esc(e.get('kind'))}</td><td><code>{_esc(e.get('source'))}</code></td><td><code>{_esc(e.get('target'))}</code></td><td>{_esc(e.get('classification') or e.get('relationship') or e.get('quality_band') or '')}</td><td>{'yes' if e.get('review_required') else 'no'}</td></tr>"
            for e in edges
        )
        metrics = graph["metrics"]
        body = f"""
        <p><a href='/cases/{_esc(case_id)}'>← Fall</a></p>
        <section class='card'>
          <h1>Analyst Graph · {_esc(case['title'])}</h1>
          <p>Read-only Projektion aus Entity-, Review-, Crawl- und Provenienz-Ledgern. Kandidatenkanten sind keine Fakten.</p>
        </section>
        <section class='grid'>
          <div class='card metric'><strong>{metrics['nodes']}</strong><span>Knoten</span></div>
          <div class='card metric'><strong>{metrics['edges']}</strong><span>Kanten</span></div>
          <div class='card metric'><strong>{metrics['review_candidate_edges']}</strong><span>Review-Kanten</span></div>
          <div class='card metric'><strong>{metrics['crawler_entity_leads']}</strong><span>Crawler-Leads</span></div>
        </section>
        <section class='card'>
          <h2>Grenzen</h2>
          <ul><li>Keine automatische Identitätsbestätigung oder Fusion.</li><li>Graph-Fokus ist offline und scope-neutral.</li><li>Crawler-Pivots nur auf bereits belegte, geprüfte Quellen und nur nach <code>NAVIGATE</code>.</li><li>Tor- und provider-spezifische Live-Gates bleiben getrennt.</li></ul>
        </section>
        <section class='card'><label>Filter <input id='filter' placeholder='entity, source, comparison…'></label></section>
        <section class='card'><h2>Knoten</h2><div class='scroll'><table><thead><tr><th>ID</th><th>Typ</th><th>Label</th><th>Review?</th></tr></thead><tbody id='nodes'>{node_rows}</tbody></table></div></section>
        <section class='card'><h2>Kanten</h2><div class='scroll'><table><thead><tr><th>Typ</th><th>Von</th><th>Zu</th><th>Status</th><th>Review?</th></tr></thead><tbody id='edges'>{edge_rows}</tbody></table></div></section>
        """
        css = "body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1280px;margin:28px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.metric strong{font-size:1.8rem;display:block}.metric span{color:#5d6876}.scroll{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #e7ebf0;text-align:left;vertical-align:top}code{font-size:.82rem}input{padding:8px;width:min(420px,80%)}a{color:#1d4ed8;text-decoration:none}"
        js = "const q=document.getElementById('filter');q.addEventListener('input',()=>{const v=q.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.style.display=r.textContent.toLowerCase().includes(v)?'':'none')});"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>Analyst Graph</title><style>{css}</style></head><body><main>{body}</main><script>{js}</script></body></html>")

    return app
