from __future__ import annotations

import html
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.version import BUILD, BUILD_NAME

COOKIE = "eagleeye349_session"
CSRF_COOKIE = "eagleeye349_csrf"
ALLOWED = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _token_file(root: Path) -> Path:
    path = root / "data/security_349/local_session_token"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path


def create_workspace_app349(*, base_dir: str | Path | None = None) -> FastAPI:
    root = Path(base_dir or Path.cwd()).resolve()
    launch_token = _token_file(root).read_text(encoding="utf-8").strip()
    session_value = secrets.token_urlsafe(32)
    csrf_value = secrets.token_urlsafe(24)
    ctx = AppContext(base_dir=root)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        try:
            yield
        finally:
            ctx.close()

    app = FastAPI(title=BUILD_NAME, version=BUILD, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.context = ctx
    app.state.base_dir = str(root)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        raw = (request.headers.get("host") or "").split(":", 1)[0].strip("[]").lower()
        client = (request.client.host if request.client else "").strip("[]").lower()
        if raw not in ALLOWED or client not in ALLOWED:
            return JSONResponse({"detail": "Loopback access only"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    def authed(request: Request) -> bool:
        return secrets.compare_digest(request.cookies.get(COOKIE, ""), session_value)

    def require_auth(request: Request) -> None:
        if not authed(request):
            raise HTTPException(status_code=401, detail="Local session required")

    def require_csrf(request: Request, submitted: str) -> None:
        require_auth(request)
        cookie = request.cookies.get(CSRF_COOKIE, "")
        if not cookie or not secrets.compare_digest(cookie, csrf_value) or not secrets.compare_digest(str(submitted or ""), csrf_value):
            raise HTTPException(status_code=403, detail="CSRF check failed")

    def shell(body: str, title: str = "EagleEye") -> HTMLResponse:
        css = "body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}.ok{color:#166534}.blocked{color:#991b1b}input,textarea,select{width:100%;box-sizing:border-box;padding:9px;margin:5px 0 10px;border:1px solid #cbd5e1;border-radius:8px}button{padding:9px 14px;border:0;border-radius:8px;background:#1f2937;color:white}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_esc(title)}</title><style>{css}</style></head><body><main>{body}</main></body></html>")

    @app.get("/health")
    def health():
        metrics = ctx.build349.schema_metrics()
        return {"ok": True, "build": BUILD, "schema_baseline": metrics["within_gate"], "tables": metrics["table"], "indexes": metrics["index"], "search_capsule": True, "opsec_intelligence_v2": True, "data_platform": True, "object_store": True, "search_backend": True, "job_engine": True, "crawler": True, "network_execution_on_boot": False, "clearnet_crawler_execution_available": True, "darknet_live_transport_available": False, "external_backend_connections_on_boot": 0}

    @app.get("/security/start")
    def security_start(token: str = ""):
        if not token or not secrets.compare_digest(token, launch_token):
            raise HTTPException(status_code=403, detail="Invalid local launch token")
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(COOKIE, session_value, httponly=True, samesite="strict", secure=False, max_age=8 * 60 * 60)
        response.set_cookie(CSRF_COOKIE, csrf_value, httponly=False, samesite="strict", secure=False, max_age=8 * 60 * 60)
        return response

    @app.get("/security/login")
    def security_login():
        return shell("<div class='card'><h1>EagleEye Build 349</h1><p>Der lokale Workspace wird nur über den geschützten Launcher geöffnet.</p></div>", "EagleEye Login")

    @app.get("/api/build349")
    def api_build349(request: Request):
        require_auth(request)
        return ctx.build349.dashboard()

    @app.get("/api/cases/{case_id}/search")
    def api_case_search(case_id: str, request: Request, q: str, limit: int = 20):
        require_auth(request)
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "query": q, "results": ctx.build349.search_case(case_id=case_id, query=q, limit=limit)}

    @app.get("/api/cases/{case_id}/jobs")
    def api_case_jobs(case_id: str, request: Request):
        require_auth(request)
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "jobs": ctx.build349.list_jobs(case_id=case_id)}

    @app.get("/api/cases/{case_id}/capsules")
    def api_capsules(case_id: str, request: Request):
        require_auth(request)
        return {"case_id": case_id, "capsules": ctx.build349.list_capsules(case_id=case_id)}

    @app.get("/api/cases/{case_id}/crawler/runs")
    def api_crawler_runs(case_id: str, request: Request):
        require_auth(request)
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "runs": ctx.build349.crawl_runs(case_id=case_id)}

    @app.get("/api/crawler/sources")
    def api_crawler_sources(request: Request):
        require_auth(request)
        return {"sources": ctx.build349.crawler_sources()}

    @app.get("/")
    def home(request: Request):
        if not authed(request):
            return RedirectResponse("/security/login", status_code=303)
        metrics = ctx.build349.schema_metrics()
        cases = ctx.cases.list_cases()
        gate = ctx.build349.qualified_gate()
        rows = "".join(f"<tr><td><a href='/cases/{_esc(c['case_id'])}'>{_esc(c['title'])}</a></td><td>{_esc(c['status'])}</td><td>{_esc(c['jurisdiction'])}</td><td>{_esc(c['created_at'])}</td></tr>" for c in cases) or "<tr><td colspan='4' class='muted'>Noch keine Fälle.</td></tr>"
        body = f"<div class='card'><h1>EagleEye · Phase 15 · Build 349</h1><p>Governed Crawler SDK: bounded read-only crawling auf Queue, Search Capsule, OPSEC-v2 und Object Store. Beim Start wird keine externe Verbindung geöffnet; Clearnet-Fetches erfolgen nur über explizit geclaimte und freigegebene Crawl-Jobs. Ein eingebauter Onion-Live-Transport ist noch nicht vorhanden.</p></div><div class='grid'><div class='card'><div class='metric'>{metrics['table']}</div><div>Tabellen</div></div><div class='card'><div class='metric'>{metrics['index']}</div><div>Indizes</div></div><div class='card'><div class='metric'>{len(ctx.build349.list_capsules(limit=500))}</div><div>Search Capsules</div></div><div class='card'><div class='metric'>MANUAL</div><div>Clearnet Crawl Gateway</div></div></div><div class='card'><b>Build Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'noch nicht belegt'} · <b>Production:</b> nicht freigegeben · <a href='/api/build349'>JSON-Status</a></div><div class='card'><h2>Fälle</h2><table><tbody>{rows}</tbody></table></div><div class='card'><h2>Neuen Fall anlegen</h2><form method='post' action='/cases'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><label>Titel</label><input name='title' required><label>Auftraggeber</label><input name='client'><label>Zweck</label><textarea name='purpose' required></textarea><label>Rechtsgrundlage</label><input name='legal_basis' required><button>Anlegen</button></form></div>"
        return shell(body)

    @app.post("/cases")
    def create_case(request: Request, title: str = Form(...), client: str = Form(""), purpose: str = Form(...), legal_basis: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        row = ctx.cases.create_case(title, client, purpose, legal_basis)
        return RedirectResponse(f"/cases/{row['case_id']}", status_code=303)

    @app.post("/cases/{case_id}/crawler/source")
    def crawler_source(case_id: str, request: Request, csrf: str = Form(...), display_name: str = Form(...), seed_url: str = Form(...), terms_ref: str = Form(...)):
        require_csrf(request, csrf); ctx.cases.get_case(case_id)
        ctx.build349.register_crawler_source(display_name=display_name, seed_urls=[seed_url], terms_ref=terms_ref)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/crawler/{source_id}/review")
    def crawler_review(case_id: str, source_id: str, request: Request, csrf: str = Form(...), rationale: str = Form(...)):
        require_csrf(request, csrf); ctx.cases.get_case(case_id)
        ctx.build349.review_crawler_source(source_id, decision="approve_read_only", rationale=rationale, reviewer=ctx.actor)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/crawler/{source_id}/enqueue")
    def crawler_enqueue(case_id: str, source_id: str, request: Request, csrf: str = Form(...)):
        require_csrf(request, csrf); ctx.cases.get_case(case_id)
        ctx.build349.enqueue_crawl(case_id=case_id, source_id=source_id)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/objects/text")
    def store_text_object(case_id: str, request: Request, content: str = Form(...), search_run_id: str = Form(""), source_id: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf)
        ctx.build349.ingest_artifact(case_id=case_id, content=content, media_type="text/plain", search_run_id=search_run_id.strip() or None, source_id=source_id.strip() or None, provenance={"ui": "build349_crawler_handoff"})
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/capsules/clearnet")
    def create_clearnet_capsule(case_id: str, request: Request, egress_hosts: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        hosts = [v.strip() for v in egress_hosts.replace(",", "\n").splitlines() if v.strip()]
        ctx.build349.create_clearnet_capsule(case_id=case_id, egress_hosts=hosts)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/source")
    def register_darknet_source(case_id: str, request: Request, onion_host: str = Form(...), display_name: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        ctx.cases.get_case(case_id)
        ctx.build349.register_darknet_source(onion_host=onion_host, display_name=display_name, source_class="research")
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/source/{source_id}/approve")
    def approve_darknet_source(case_id: str, source_id: str, request: Request, rationale: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        ctx.cases.get_case(case_id)
        ctx.build349.review_darknet_source(source_id, decision="approve_read_only", rationale=rationale, reviewer=ctx.actor)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/research")
    def create_darknet_research(case_id: str, request: Request, query: str = Form(...), source_ids: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        ids = [v.strip() for v in source_ids.replace(",", "\n").splitlines() if v.strip()]
        ctx.build349.create_darknet_research(case_id=case_id, query=query, source_ids=ids, human_approved=True)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/capsules/{search_run_id}/preflight")
    def preflight(search_run_id: str, request: Request, url: str = Form(...), source_id: str = Form(""), resolved_ip: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf)
        capsule = ctx.db.one("SELECT search_kind FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        ips = [] if capsule and capsule['search_kind'] == 'darknet' else ([resolved_ip.strip()] if resolved_ip.strip() else [])
        result = ctx.build349.preflight_request(search_run_id, url=url, source_id=source_id or None, resolved_ips=ips, browser_webrtc_disabled=True, dns_via_approved_profile=True)
        capsule = ctx.db.one("SELECT case_id FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not capsule:
            raise HTTPException(status_code=404, detail="Capsule not found")
        return RedirectResponse(f"/cases/{capsule['case_id']}?preflight={result.get('final_disposition', result['disposition'])}", status_code=303)

    @app.post("/capsules/{search_run_id}/close")
    def close_capsule(search_run_id: str, request: Request, csrf: str = Form(...)):
        require_csrf(request, csrf)
        capsule = ctx.db.one("SELECT case_id FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not capsule:
            raise HTTPException(status_code=404, detail="Capsule not found")
        ctx.build349.close_capsule(search_run_id)
        return RedirectResponse(f"/cases/{capsule['case_id']}", status_code=303)

    @app.get("/api/capsules/{search_run_id}/opsec-v2")
    def api_opsec_v2(search_run_id: str, request: Request):
        require_auth(request)
        return {"search_run_id": search_run_id, "assessments": ctx.build349.assessments(search_run_id)}

    @app.post("/cases/{case_id}/search/local")
    def local_search_index(case_id: str, request: Request, title: str = Form(...), text: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf)
        ctx.cases.get_case(case_id)
        ctx.build349.index_local_text(case_id=case_id, title=title, text=text, provenance={"ui": "build349_local_index"})
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.get("/cases/{case_id}/search")
    def case_search(case_id: str, request: Request, q: str):
        require_auth(request)
        case = ctx.cases.get_case(case_id)
        results = ctx.build349.search_case(case_id=case_id, query=q, limit=50)
        rows = "".join(f"<tr><td>{_esc(r['title'])}</td><td>{_esc(r['snippet'])}</td><td>{float(r['score']):.3f}</td><td><code>{_esc(r['object_id'])}</code></td></tr>" for r in results) or "<tr><td colspan='4' class='muted'>Keine Treffer.</td></tr>"
        return shell(f"<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Suche: {_esc(q)}</h1><table><thead><tr><th>Titel</th><th>Treffer</th><th>Score</th><th>Object</th></tr></thead><tbody>{rows}</tbody></table></div>", case['title'])

    @app.get("/cases/{case_id}")
    def case_detail(case_id: str, request: Request):
        require_auth(request)
        try:
            case = ctx.cases.get_case(case_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Case not found")
        capsules = ctx.build349.list_capsules(case_id=case_id, limit=100)
        sources = ctx.db.all("SELECT source_id,locator,display_name,review_status FROM phase15_sources WHERE source_kind='darknet_onion' ORDER BY created_at DESC LIMIT 100")
        decision_count = int(ctx.db.one("SELECT COUNT(*) c FROM phase15_opsec_decisions d JOIN phase15_search_capsules c ON c.search_run_id=d.search_run_id WHERE c.case_id=?", (case_id,))["c"])
        counts = {
            "targets": ctx.db.one("SELECT COUNT(*) c FROM targets WHERE case_id=?", (case_id,))["c"],
            "evidence": ctx.db.one("SELECT COUNT(*) c FROM evidence_items WHERE case_id=?", (case_id,))["c"],
            "tasks": ctx.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=?", (case_id,))["c"],
            "capsules": len(capsules),
            "opsec decisions": decision_count,
            "jobs": len(ctx.build349.list_jobs(case_id=case_id, limit=500)),
            "indexed": len(ctx.build349.search_case(case_id=case_id, query="*", limit=1)) if False else int(ctx.db.one("SELECT COUNT(*) c FROM phase15_search_documents WHERE case_id=?", (case_id,))["c"]),
        }
        source_rows = "".join(f"<tr><td><code>{_esc(s['source_id'])}</code></td><td>{_esc(s['display_name'])}</td><td><code>{_esc(s['locator'])}</code></td><td>{_esc(s['review_status'])}</td><td>{'' if s['review_status']=='approved_read_only' else f'''<form method='post' action='/cases/{_esc(case_id)}/darknet/source/{_esc(s['source_id'])}/approve'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><input name='rationale' value='human reviewed for public/authorized read-only research' required><button>Approve read-only</button></form>'''}</td></tr>" for s in sources) or "<tr><td colspan='5' class='muted'>Keine Onion-Quellen registriert.</td></tr>"
        capsule_rows = ""
        for c in capsules:
            decisions = ctx.build349.decisions(c["search_run_id"])
            last = decisions[-1]["disposition"] if decisions else "none"
            actions = ""
            if c["capsule_state"] == "active":
                actions = f"<form method='post' action='/capsules/{_esc(c['search_run_id'])}/preflight'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><input name='url' placeholder='https://example.org/ oder http://...onion/' required><input name='source_id' placeholder='source_id bei Onion'><input name='resolved_ip' placeholder='Clearnet: vom Gateway geprüfte Ziel-IP; Onion leer'><button>OPSEC-v2-Preflight</button></form><form method='post' action='/capsules/{_esc(c['search_run_id'])}/close'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><button>Capsule schließen</button></form>"
            capsule_rows += f"<tr><td><code>{_esc(c['search_run_id'])}</code></td><td>{_esc(c['search_kind'])}</td><td>{_esc(c['capsule_state'])}</td><td>{_esc(c['network_profile_ref'])}</td><td>{_esc(last)}</td><td>{actions}</td></tr>"
        capsule_rows = capsule_rows or "<tr><td colspan='6' class='muted'>Noch keine Search Capsules.</td></tr>"
        body = f"<p><a href='/'>← Übersicht</a></p><div class='card'><h1>{_esc(case['title'])}</h1><p>{_esc(case['purpose'])}</p></div><div class='grid'>" + "".join(f"<div class='card'><div class='metric'>{v}</div><div>{_esc(k)}</div></div>" for k, v in counts.items()) + "</div>" + ctx.build349.render_workspace_panel(case_id=case_id, csrf=csrf_value) + f"<div class='card'><h2>Clearnet Search Capsule</h2><form method='post' action='/cases/{_esc(case_id)}/capsules/clearnet'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><label>Exakte erlaubte Hosts, einer pro Zeile</label><textarea name='egress_hosts' placeholder='example.org\nexample.com' required></textarea><button>Capsule anlegen</button></form></div><div class='card'><h2>Darknet Source Governance</h2><form method='post' action='/cases/{_esc(case_id)}/darknet/source'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><label>v3 Onion Host</label><input name='onion_host' required><label>Anzeigename</label><input name='display_name' required><button>Quelle registrieren</button></form><table><thead><tr><th>ID</th><th>Name</th><th>Host</th><th>Review</th><th>Aktion</th></tr></thead><tbody>{source_rows}</tbody></table></div><div class='card'><h2>Darknet Research Capsule</h2><p>Nur bereits menschlich freigegebene read-only Onion-Quellen. Es wird noch keine Tor-Verbindung geöffnet.</p><form method='post' action='/cases/{_esc(case_id)}/darknet/research'><input type='hidden' name='csrf' value='{_esc(csrf_value)}'><label>Rechercheauftrag</label><textarea name='query' required></textarea><label>Source IDs, eine pro Zeile</label><textarea name='source_ids' required></textarea><button>Reviewte Capsule + Agent Task anlegen</button></form></div><div class='card'><h2>Capsules & Request-Preflights</h2><table><thead><tr><th>Run</th><th>Typ</th><th>Status</th><th>Profil</th><th>Letzte Entscheidung</th><th>Aktion</th></tr></thead><tbody>{capsule_rows}</tbody></table></div>"
        return shell(body, case["title"])

    return app
