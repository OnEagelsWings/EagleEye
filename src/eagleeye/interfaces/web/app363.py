from __future__ import annotations

import html
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from eagleeye_pro.core.app_context import AppContext
from eagleeye_pro.version import BUILD, BUILD_NAME

COOKIE = "ee_auth_session"
CSRF_COOKIE = "ee_auth_csrf"
ALLOWED = {"127.0.0.1", "localhost", "::1", "testclient", "testserver"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _token_file(root: Path) -> Path:
    path = root / "data/security_363/local_session_token"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path


def create_workspace_app363(*, base_dir: str | Path | None = None) -> FastAPI:
    root = Path(base_dir or Path.cwd()).resolve()
    launch_token = _token_file(root).read_text(encoding="utf-8").strip()
    ctx = AppContext(base_dir=root)
    team_identity = ctx.team_identity_359
    launch_cookie = secrets.token_urlsafe(32)

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

    def client_fingerprint(request: Request) -> str:
        import hashlib
        material="|".join((request.headers.get("user-agent",""),request.headers.get("accept-language",""),(request.client.host if request.client else "")))
        return hashlib.sha256(material.encode("utf-8",errors="replace")).hexdigest()

    def identity(request: Request, *, touch: bool = True) -> dict[str, Any] | None:
        current=getattr(request.state,"team360_identity",None)
        if current:return current
        item=team_identity.validate_session(request.cookies.get(COOKIE,""),client_fingerprint=client_fingerprint(request),touch=touch)
        if item:request.state.team360_identity=item
        return item

    def authed(request: Request) -> bool:
        return identity(request) is not None

    def require_auth(request: Request) -> dict[str, Any]:
        item=identity(request)
        if not item:raise HTTPException(status_code=401,detail="Anmeldung erforderlich oder Sitzung abgelaufen")
        return item

    def require_csrf(request: Request, submitted: str) -> dict[str, Any]:
        item=require_auth(request); cookie=request.cookies.get(CSRF_COOKIE,""); token=request.cookies.get(COOKIE,"")
        if not cookie or not secrets.compare_digest(cookie,str(submitted or "")) or not team_identity.csrf_token_valid(item,cookie):
            raise HTTPException(status_code=403,detail="CSRF check failed")
        return item

    def require_case(request: Request, case_id: str, capability: str) -> dict[str, Any]:
        item=require_auth(request)
        try:ctx.build363.authorize(item,case_id=case_id,capability=capability)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))
        return item

    def media_case_id(media_id: str) -> str:
        row=ctx.db.one("SELECT case_id FROM phase15_media_assets WHERE media_id=?",(media_id,))
        if not row:raise HTTPException(status_code=404,detail="Image not found")
        return str(row["case_id"])

    def job_case_id(job_id: str) -> str:
        row=ctx.db.one("SELECT case_id FROM phase15_jobs WHERE job_id=?",(job_id,))
        if not row:raise HTTPException(status_code=404,detail="Job not found")
        return str(row["case_id"])

    def capsule_case_id(search_run_id: str) -> str:
        row=ctx.db.one("SELECT case_id FROM phase15_search_capsules WHERE search_run_id=?",(search_run_id,))
        if not row:raise HTTPException(status_code=404,detail="Capsule not found")
        return str(row["case_id"])

    def shell(body: str, title: str = "EagleEye") -> HTMLResponse:
        css = "body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#f5f7fa;color:#18202a}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dce2ea;border-radius:12px;padding:18px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metric{font-size:1.8rem;font-weight:700}.muted{color:#667085}.ok{color:#166534}.blocked{color:#991b1b}input,textarea,select{width:100%;box-sizing:border-box;padding:9px;margin:5px 0 10px;border:1px solid #cbd5e1;border-radius:8px}button{padding:9px 14px;border:0;border-radius:8px;background:#1f2937;color:white}a{color:#1d4ed8;text-decoration:none}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;font-size:.92rem;vertical-align:top}code{background:#eef2f7;padding:2px 5px;border-radius:4px;word-break:break-all}"
        return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_esc(title)}</title><style>{css}</style></head><body><main>{body}</main></body></html>")

    @app.get("/health")
    def health():
        metrics = ctx.build363.schema_metrics()
        return {"ok": True, "build": BUILD, "schema_baseline": metrics["within_gate"], "tables": metrics["table"], "indexes": metrics["index"], "search_capsule": True, "opsec_intelligence_v2": True, "data_platform": True, "object_store": True, "search_backend": True, "job_engine": True, "crawler": True, "image_intelligence": True, "image_metadata": True, "ocr_explicit": True, "image_similarity": True, "perceptual_hashing": True, "local_visual_descriptor": True, "visual_geolocation": True, "manipulation_signals": True, "visual_context_crawler": True, "media_crawler": True, "ai_investigation_supervisor": True, "multi_wave_research": True, "max_research_waves": 4, "ai_dossier": True, "speech_output_local": True, "voice_input": True, "voice_input_mode": "push_to_talk_local_stt_adapter", "voice_transcript_editable": True, "voice_external_actions_confirmed": True, "network_execution_on_boot": False, "clearnet_crawler_execution_available": True, "darknet_live_transport_available": False, "external_backend_connections_on_boot": 0, "team_rbac": True, "four_eyes_dossier_export": True, "remote_team_mode": False}

    @app.get("/api/build363/phase16-status")
    def phase16_status(request: Request):
        require_auth(request)
        return ctx.build363.phase16_status()

    @app.post("/api/cases/{case_id}/phase16/autonomous-cycle")
    async def phase16_autonomous_cycle(case_id: str, request: Request):
        require_case(request,case_id,"research.run")
        body=await request.json()
        return ctx.build363.run_autonomous_investigation(case_id=case_id,max_ticks=int(body.get("max_ticks",8)))

    @app.post("/api/cases/{case_id}/phase16/opsec-protect")
    async def phase16_opsec_protect(case_id: str, request: Request):
        require_case(request,case_id,"research.run")
        return ctx.build363.autonomous_opsec_protect(case_id=case_id)

    @app.get("/security/start")
    def security_start(token: str = ""):
        if not token or not secrets.compare_digest(token,launch_token):
            raise HTTPException(status_code=403,detail="Invalid local launch token")
        target="/security/bootstrap" if team_identity.bootstrap_required() else "/security/login"
        response=RedirectResponse(target,status_code=303)
        response.set_cookie("ee_launch_363",launch_cookie,httponly=True,samesite="strict",secure=False,max_age=15*60)
        return response

    def launch_authorized(request: Request) -> bool:
        return secrets.compare_digest(request.cookies.get("ee_launch_363",""),launch_cookie)

    @app.get("/security/bootstrap")
    def security_bootstrap(request: Request):
        if not launch_authorized(request) or not team_identity.bootstrap_required():
            raise HTTPException(status_code=403,detail="Bootstrap unavailable")
        return shell("<div class='card'><h1>EagleEye Build 363 · Erstkonfiguration</h1><form method='post' action='/security/bootstrap'><label>Benutzername</label><input name='username' required><label>Anzeigename</label><input name='display_name' required><label>Passwort (mind. 15 Zeichen)</label><input type='password' name='password' required><button>Systemadministrator anlegen</button></form></div>","EagleEye Bootstrap")

    @app.post("/security/bootstrap")
    def security_bootstrap_post(request: Request,username: str=Form(...),display_name: str=Form(...),password: str=Form(...)):
        if not launch_authorized(request) or not team_identity.bootstrap_required():
            raise HTTPException(status_code=403,detail="Bootstrap unavailable")
        try:team_identity.create_initial_admin(username=username,display_name=display_name,password=password)
        except Exception as exc:raise HTTPException(status_code=400,detail=str(exc))
        return RedirectResponse("/security/login",status_code=303)

    @app.get("/security/login")
    def security_login(request: Request):
        if not launch_authorized(request):raise HTTPException(status_code=403,detail="Launcher authorization required")
        if team_identity.bootstrap_required():return RedirectResponse("/security/bootstrap",status_code=303)
        return shell("<div class='card'><h1>EagleEye Build 363 · Team Login</h1><form method='post' action='/security/login'><label>Benutzername</label><input name='username' required><label>Passwort</label><input type='password' name='password' required><button>Anmelden</button></form></div>","EagleEye Login")

    @app.post("/security/login")
    def security_login_post(request: Request,username: str=Form(...),password: str=Form(...)):
        if not launch_authorized(request):raise HTTPException(status_code=403,detail="Launcher authorization required")
        issued=team_identity.authenticate(username=username,password=password,client_fingerprint=client_fingerprint(request))
        if not issued:raise HTTPException(status_code=401,detail="Anmeldung fehlgeschlagen")
        response=RedirectResponse("/",status_code=303)
        response.set_cookie(COOKIE,issued.token,httponly=True,samesite="strict",secure=False,max_age=issued.max_age)
        response.set_cookie(CSRF_COOKIE,issued.csrf_token,httponly=False,samesite="strict",secure=False,max_age=issued.max_age)
        return response

    @app.post("/security/logout")
    def security_logout(request: Request,csrf: str=Form(...)):
        item=require_csrf(request,csrf);team_identity.revoke_session(request.cookies.get(COOKIE,""),reason="user_logout")
        response=RedirectResponse("/security/login",status_code=303);response.delete_cookie(COOKIE);response.delete_cookie(CSRF_COOKIE);return response

    @app.get("/api/build363")
    def api_build352(request: Request):
        require_auth(request)
        return ctx.build363.dashboard()

    @app.get("/api/cases/{case_id}/ai/waves")
    def api_case_ai_waves(case_id: str, request: Request):
        require_case(request,case_id,"case.read"); ctx.cases.get_case(case_id)
        return {"case_id": case_id, "waves": ctx.build363.investigation_research_waves(case_id)}

    @app.post("/cases/{case_id}/ai/wave/evaluate")
    def ai_wave_evaluate(case_id: str, request: Request, csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"voice.research"); ctx.cases.get_case(case_id)
        ctx.build363.evaluate_investigation_wave(case_id=case_id, allow_followup=True)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.get("/api/cases/{case_id}/search")
    def api_case_search(case_id: str, request: Request, q: str, limit: int = 20):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "query": q, "results": ctx.build363.search_case(case_id=case_id, query=q, limit=limit)}

    @app.get("/api/cases/{case_id}/jobs")
    def api_case_jobs(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "jobs": ctx.build363.list_jobs(case_id=case_id)}

    @app.get("/api/jobs/{job_id}/frontier")
    def api_job_frontier(job_id: str, request: Request):
        require_case(request,job_case_id(job_id),"case.read")
        try: return ctx.build363.frontier_checkpoint(job_id)
        except KeyError: raise HTTPException(status_code=404, detail="Job not found")

    @app.get("/api/cases/{case_id}/images")
    def api_case_images(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "images": ctx.build363.image_assets(case_id=case_id)}

    @app.get("/api/images/{media_id}")
    def api_image(media_id: str, request: Request):
        require_case(request,media_case_id(media_id),"case.read")
        try: return ctx.build363.image_asset(media_id)
        except KeyError: raise HTTPException(status_code=404, detail="Image not found")

    @app.get("/api/images/{media_id}/similarity")
    def api_image_similarity(media_id: str, request: Request):
        require_case(request,media_case_id(media_id),"case.read")
        try: return ctx.build363.analyze_similarity(media_id)
        except KeyError: raise HTTPException(status_code=404, detail="Image not found")

    @app.get("/api/cases/{case_id}/image-links")
    def api_case_image_links(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "links": ctx.build363.similarity_links(case_id=case_id)}

    @app.get("/api/cases/{case_id}/geo-links")
    def api_case_geo_links(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "links": ctx.build363.geolocation_links(case_id=case_id)}

    @app.get("/api/images/{media_id}/visual-context")
    def api_image_visual_context(media_id: str, request: Request):
        require_case(request,media_case_id(media_id),"case.read")
        try: return ctx.build363.visual_context.context_for_media(media_id)
        except KeyError: raise HTTPException(status_code=404, detail="Image not found")

    @app.post("/api/images/{media_id}/geo-analyze")
    async def api_image_geo_analyze(media_id: str, request: Request):
        require_case(request,media_case_id(media_id),"research.run")
        body = await request.json()
        if not bool(body.get("human_approved")):
            raise HTTPException(status_code=403, detail="Explicit human approval required")
        try:
            return ctx.build363.analyze_visual_geolocation(media_id, cues=body.get("cues") or [], include_source_context=bool(body.get("include_source_context", True)), include_landmark_references=bool(body.get("include_landmark_references", True)), human_approved=True)
        except KeyError: raise HTTPException(status_code=404, detail="Image not found")
        except (ValueError, PermissionError) as exc: raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/images/{media_id}/landmark-reference")
    async def api_landmark_reference(media_id: str, request: Request):
        require_case(request,media_case_id(media_id),"research.run")
        body = await request.json()
        if not bool(body.get("human_approved")):
            raise HTTPException(status_code=403, detail="Explicit human approval required")
        try:
            return ctx.build363.register_landmark_reference(media_id=media_id, label=str(body.get("label") or ""), city=str(body.get("city") or ""), country=str(body.get("country") or ""), latitude=body.get("latitude"), longitude=body.get("longitude"), human_approved=True)
        except KeyError: raise HTTPException(status_code=404, detail="Image not found")
        except (ValueError, PermissionError) as exc: raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/cases/{case_id}/images")
    async def upload_image(case_id: str, request: Request, image: UploadFile = File(...), search_run_id: str = Form(""), source_id: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        ctx.cases.get_case(case_id)
        data = await image.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large")
        try:
            ctx.build363.ingest_image(case_id=case_id, content=data, declared_media_type=image.content_type or "", filename=image.filename or "", search_run_id=search_run_id.strip() or None, source_id=source_id.strip() or None, provenance={"ui": "build363_image_upload"})
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.get("/api/cases/{case_id}/capsules")
    def api_capsules(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        return {"case_id": case_id, "capsules": ctx.build363.list_capsules(case_id=case_id)}

    @app.get("/api/cases/{case_id}/crawler/runs")
    def api_crawler_runs(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        ctx.cases.get_case(case_id)
        return {"case_id": case_id, "runs": ctx.build363.crawl_runs(case_id=case_id)}

    @app.get("/api/crawler/sources")
    def api_crawler_sources(request: Request):
        require_auth(request)
        return {"sources": ctx.build363.crawler_sources()}

    @app.post("/api/cases/{case_id}/voice/propose")
    async def api_voice_propose(case_id: str, request: Request):
        item=require_case(request,case_id,"voice.read"); ctx.cases.get_case(case_id); body=await request.json()
        try: return ctx.build363.team_voice_propose(identity=item,case_id=case_id, transcript=str(body.get("transcript") or ""), mode=str(body.get("mode") or "command"), source="workspace_transcript")
        except (ValueError, PermissionError) as exc: raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/cases/{case_id}/voice/transcribe")
    async def api_voice_transcribe(case_id: str, request: Request, audio: UploadFile = File(...), mode: str = Form("command"), human_started: str = Form("false"), language: str = Form("de")):
        item=require_case(request,case_id,"voice.read"); ctx.cases.get_case(case_id)
        data=await audio.read(15*1024*1024+1)
        try: return ctx.build363.team_voice_transcribe(identity=item,case_id=case_id,audio=data,media_type=audio.content_type or "",language=language,human_started=str(human_started).casefold()=="true",mode=mode)
        except (ValueError, PermissionError) as exc: raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/voice/{intent_id}/execute")
    async def api_voice_execute(intent_id: str, request: Request):
        item=require_auth(request); body=await request.json()
        try: return ctx.build363.team_voice_execute(identity=item,intent_id=intent_id,confirmed=bool(body.get("confirmed")),edited_transcript=body.get("edited_transcript"))
        except KeyError: raise HTTPException(status_code=404,detail="Voice intent not found")
        except (ValueError, PermissionError) as exc: raise HTTPException(status_code=400,detail=str(exc))

    @app.get("/api/cases/{case_id}/voice/interactions")
    def api_voice_interactions(case_id: str, request: Request):
        require_case(request,case_id,"voice.read"); ctx.cases.get_case(case_id); return {"case_id":case_id,"interactions":ctx.build363.voice_interactions(case_id)}

    @app.get("/")
    def home(request: Request):
        if not authed(request):
            return RedirectResponse("/security/login", status_code=303)
        metrics = ctx.build363.schema_metrics()
        user=require_auth(request)
        cases = ctx.build363.visible_cases(user)
        gate = ctx.build363.qualified_gate()
        rows = "".join(f"<tr><td><a href='/cases/{_esc(c['case_id'])}'>{_esc(c['title'])}</a></td><td>{_esc(c['status'])}</td><td>{_esc(c['jurisdiction'])}</td><td>{_esc(c['created_at'])}</td></tr>" for c in cases) or "<tr><td colspan='4' class='muted'>Noch keine Fälle.</td></tr>"
        body = f"<div class='card'><h1>EagleEye · Phase 15 · Build 363</h1><p>AI-Ermittlung v356: Intake, explizites GO, governte Research-Waves, Crawler-Monitoring, Cross-Modal Fusion, Hypothesen und evidence-first Dossier. Lokale Browser-Sprachausgabe; Voice Input 358: Push-to-talk, editierbares Transkript und bestätigungspflichtige Sprachbefehle.</p></div><div class='grid'><div class='card'><div class='metric'>{metrics['table']}</div><div>Tabellen</div></div><div class='card'><div class='metric'>{metrics['index']}</div><div>Indizes</div></div><div class='card'><div class='metric'>{len(ctx.build363.list_capsules(limit=500))}</div><div>Search Capsules</div></div><div class='card'><div class='metric'>MANUAL</div><div>Clearnet Crawl Gateway</div></div></div><div class='card'><b>Build Gate:</b> {'PASS' if gate['build_acceptance_ready'] else 'noch nicht belegt'} · <b>Production:</b> nicht freigegeben · <a href='/api/build363'>JSON-Status</a></div><div class='card'><h2>Fälle</h2><table><tbody>{rows}</tbody></table></div><div class='card'><h2>Neuen Fall anlegen</h2><form method='post' action='/cases'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><label>Titel</label><input name='title' required><label>Auftraggeber</label><input name='client'><label>Zweck</label><textarea name='purpose' required></textarea><label>Rechtsgrundlage</label><input name='legal_basis' required><button>Anlegen</button></form></div>"
        return shell(body)

    @app.post("/cases")
    def create_case(request: Request, title: str = Form(...), client: str = Form(""), purpose: str = Form(...), legal_basis: str = Form(...), csrf: str = Form(...)):
        item=require_csrf(request, csrf)
        try:row=ctx.build363.team_create_case(identity=item,title=title,client=client,purpose=purpose,legal_basis=legal_basis)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))
        return RedirectResponse(f"/cases/{row['case_id']}", status_code=303)

    @app.post("/cases/{case_id}/crawler/source")
    def crawler_source(case_id: str, request: Request, csrf: str = Form(...), display_name: str = Form(...), seed_url: str = Form(...), terms_ref: str = Form(...), sitemap_url: str = Form(""), archive_seed_url: str = Form("")):
        require_csrf(request, csrf); require_case(request,case_id,"research.run"); ctx.cases.get_case(case_id)
        ctx.build363.register_crawler_source(display_name=display_name, seed_urls=[seed_url], terms_ref=terms_ref, sitemap_urls=[sitemap_url.strip()] if sitemap_url.strip() else [], archive_seed_urls=[archive_seed_url.strip()] if archive_seed_url.strip() else [])
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/connectors/official")
    def official_connector(case_id: str, request: Request, csrf: str = Form(...), connector_key: str = Form(...), identifier: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run"); ctx.cases.get_case(case_id)
        try:
            result = ctx.build363.register_official_source(connector_key, identifier)
        except PermissionError:
            # Authenticated providers remain plan-only; expose the plan without storing credentials.
            result = {"plan": ctx.build363.connector_source_plan(connector_key, identifier)}
        return RedirectResponse(f"/cases/{case_id}?connector={result['plan']['connector_key']}", status_code=303)

    @app.post("/cases/{case_id}/crawler/{source_id}/review")
    def crawler_review(case_id: str, source_id: str, request: Request, csrf: str = Form(...), rationale: str = Form(...)):
        item=require_csrf(request, csrf); ctx.cases.get_case(case_id)
        try:ctx.build363.team_review_crawler_source(identity=item,case_id=case_id,source_id=source_id,decision="approve_read_only",rationale=rationale)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/crawler/{source_id}/enqueue")
    def crawler_enqueue(case_id: str, source_id: str, request: Request, csrf: str = Form(...)):
        item=require_csrf(request, csrf); ctx.cases.get_case(case_id)
        try:ctx.build363.team_enqueue_crawl(identity=item,case_id=case_id,source_id=source_id)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/objects/text")
    def store_text_object(case_id: str, request: Request, content: str = Form(...), search_run_id: str = Form(""), source_id: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        ctx.build363.ingest_artifact(case_id=case_id, content=content, media_type="text/plain", search_run_id=search_run_id.strip() or None, source_id=source_id.strip() or None, provenance={"ui": "build363_crawler_handoff"})
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/capsules/clearnet")
    def create_clearnet_capsule(case_id: str, request: Request, egress_hosts: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        hosts = [v.strip() for v in egress_hosts.replace(",", "\n").splitlines() if v.strip()]
        ctx.build363.create_clearnet_capsule(case_id=case_id, egress_hosts=hosts)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/source")
    def register_darknet_source(case_id: str, request: Request, onion_host: str = Form(...), display_name: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        ctx.cases.get_case(case_id)
        ctx.build363.register_darknet_source(onion_host=onion_host, display_name=display_name, source_class="research")
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/source/{source_id}/approve")
    def approve_darknet_source(case_id: str, source_id: str, request: Request, rationale: str = Form(...), csrf: str = Form(...)):
        item=require_csrf(request, csrf); require_case(request,case_id,"source.review")
        ctx.cases.get_case(case_id)
        ctx.build363.review_darknet_source(source_id, decision="approve_read_only", rationale=rationale, reviewer=item["username"])
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/darknet/research")
    def create_darknet_research(case_id: str, request: Request, query: str = Form(...), source_ids: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        ids = [v.strip() for v in source_ids.replace(",", "\n").splitlines() if v.strip()]
        ctx.build363.create_darknet_research(case_id=case_id, query=query, source_ids=ids, human_approved=True)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/capsules/{search_run_id}/preflight")
    def preflight(search_run_id: str, request: Request, url: str = Form(...), source_id: str = Form(""), resolved_ip: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,capsule_case_id(search_run_id),"research.run")
        capsule = ctx.db.one("SELECT search_kind FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        ips = [] if capsule and capsule['search_kind'] == 'darknet' else ([resolved_ip.strip()] if resolved_ip.strip() else [])
        result = ctx.build363.preflight_request(search_run_id, url=url, source_id=source_id or None, resolved_ips=ips, browser_webrtc_disabled=True, dns_via_approved_profile=True)
        capsule = ctx.db.one("SELECT case_id FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not capsule:
            raise HTTPException(status_code=404, detail="Capsule not found")
        return RedirectResponse(f"/cases/{capsule['case_id']}?preflight={result.get('final_disposition', result['disposition'])}", status_code=303)

    @app.post("/capsules/{search_run_id}/close")
    def close_capsule(search_run_id: str, request: Request, csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,capsule_case_id(search_run_id),"research.run")
        capsule = ctx.db.one("SELECT case_id FROM phase15_search_capsules WHERE search_run_id=?", (search_run_id,))
        if not capsule:
            raise HTTPException(status_code=404, detail="Capsule not found")
        ctx.build363.close_capsule(search_run_id)
        return RedirectResponse(f"/cases/{capsule['case_id']}", status_code=303)

    @app.get("/api/capsules/{search_run_id}/opsec-v2")
    def api_opsec_v2(search_run_id: str, request: Request):
        require_case(request,capsule_case_id(search_run_id),"case.read")
        return {"search_run_id": search_run_id, "assessments": ctx.build363.assessments(search_run_id)}

    @app.post("/cases/{case_id}/search/local")
    def local_search_index(case_id: str, request: Request, title: str = Form(...), text: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"research.run")
        ctx.cases.get_case(case_id)
        ctx.build363.index_local_text(case_id=case_id, title=title, text=text, provenance={"ui": "build363_local_index"})
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.get("/cases/{case_id}/search")
    def case_search(case_id: str, request: Request, q: str):
        require_case(request,case_id,"case.read")
        case = ctx.cases.get_case(case_id)
        results = ctx.build363.search_case(case_id=case_id, query=q, limit=50)
        rows = "".join(f"<tr><td>{_esc(r['title'])}</td><td>{_esc(r['snippet'])}</td><td>{float(r['score']):.3f}</td><td><code>{_esc(r['object_id'])}</code></td></tr>" for r in results) or "<tr><td colspan='4' class='muted'>Keine Treffer.</td></tr>"
        return shell(f"<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>Suche: {_esc(q)}</h1><table><thead><tr><th>Titel</th><th>Treffer</th><th>Score</th><th>Object</th></tr></thead><tbody>{rows}</tbody></table></div>", case['title'])

    @app.get("/cases/{case_id}")
    def case_detail(case_id: str, request: Request):
        item=require_case(request,case_id,"case.read")
        try:
            case = ctx.cases.get_case(case_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Case not found")
        capsules = ctx.build363.list_capsules(case_id=case_id, limit=100)
        sources = ctx.db.all("SELECT source_id,locator,display_name,review_status FROM phase15_sources WHERE source_kind='darknet_onion' ORDER BY created_at DESC LIMIT 100")
        decision_count = int(ctx.db.one("SELECT COUNT(*) c FROM phase15_opsec_decisions d JOIN phase15_search_capsules c ON c.search_run_id=d.search_run_id WHERE c.case_id=?", (case_id,))["c"])
        counts = {
            "targets": ctx.db.one("SELECT COUNT(*) c FROM targets WHERE case_id=?", (case_id,))["c"],
            "evidence": ctx.db.one("SELECT COUNT(*) c FROM evidence_items WHERE case_id=?", (case_id,))["c"],
            "tasks": ctx.db.one("SELECT COUNT(*) c FROM phase15_agent_tasks WHERE case_id=?", (case_id,))["c"],
            "capsules": len(capsules),
            "opsec decisions": decision_count,
            "jobs": len(ctx.build363.list_jobs(case_id=case_id, limit=500)),
            "indexed": len(ctx.build363.search_case(case_id=case_id, query="*", limit=1)) if False else int(ctx.db.one("SELECT COUNT(*) c FROM phase15_search_documents WHERE case_id=?", (case_id,))["c"]),
        }
        source_rows = "".join(f"<tr><td><code>{_esc(s['source_id'])}</code></td><td>{_esc(s['display_name'])}</td><td><code>{_esc(s['locator'])}</code></td><td>{_esc(s['review_status'])}</td><td>{'' if s['review_status']=='approved_read_only' else f'''<form method='post' action='/cases/{_esc(case_id)}/darknet/source/{_esc(s['source_id'])}/approve'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><input name='rationale' value='human reviewed for public/authorized read-only research' required><button>Approve read-only</button></form>'''}</td></tr>" for s in sources) or "<tr><td colspan='5' class='muted'>Keine Onion-Quellen registriert.</td></tr>"
        capsule_rows = ""
        for c in capsules:
            decisions = ctx.build363.decisions(c["search_run_id"])
            last = decisions[-1]["disposition"] if decisions else "none"
            actions = ""
            if c["capsule_state"] == "active":
                actions = f"<form method='post' action='/capsules/{_esc(c['search_run_id'])}/preflight'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><input name='url' placeholder='https://example.org/ oder http://...onion/' required><input name='source_id' placeholder='source_id bei Onion'><input name='resolved_ip' placeholder='Clearnet: vom Gateway geprüfte Ziel-IP; Onion leer'><button>OPSEC-v2-Preflight</button></form><form method='post' action='/capsules/{_esc(c['search_run_id'])}/close'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><button>Capsule schließen</button></form>"
            capsule_rows += f"<tr><td><code>{_esc(c['search_run_id'])}</code></td><td>{_esc(c['search_kind'])}</td><td>{_esc(c['capsule_state'])}</td><td>{_esc(c['network_profile_ref'])}</td><td>{_esc(last)}</td><td>{actions}</td></tr>"
        capsule_rows = capsule_rows or "<tr><td colspan='6' class='muted'>Noch keine Search Capsules.</td></tr>"
        body = f"<p><a href='/'>← Übersicht</a></p><div class='card'><h1>{_esc(case['title'])}</h1><p>{_esc(case['purpose'])}</p></div><div class='grid'>" + "".join(f"<div class='card'><div class='metric'>{v}</div><div>{_esc(k)}</div></div>" for k, v in counts.items()) + "</div>" + ctx.build363.render_workspace_panel(case_id=case_id, csrf=request.cookies.get(CSRF_COOKIE,""), identity=item) + f"<div class='card'><h2>Clearnet Search Capsule</h2><form method='post' action='/cases/{_esc(case_id)}/capsules/clearnet'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><label>Exakte erlaubte Hosts, einer pro Zeile</label><textarea name='egress_hosts' placeholder='example.org\nexample.com' required></textarea><button>Capsule anlegen</button></form></div><div class='card'><h2>Darknet Source Governance</h2><form method='post' action='/cases/{_esc(case_id)}/darknet/source'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><label>v3 Onion Host</label><input name='onion_host' required><label>Anzeigename</label><input name='display_name' required><button>Quelle registrieren</button></form><table><thead><tr><th>ID</th><th>Name</th><th>Host</th><th>Review</th><th>Aktion</th></tr></thead><tbody>{source_rows}</tbody></table></div><div class='card'><h2>Darknet Research Capsule</h2><p>Nur bereits menschlich freigegebene read-only Onion-Quellen. Es wird noch keine Tor-Verbindung geöffnet.</p><form method='post' action='/cases/{_esc(case_id)}/darknet/research'><input type='hidden' name='csrf' value='{_esc(request.cookies.get(CSRF_COOKIE,""))}'><label>Rechercheauftrag</label><textarea name='query' required></textarea><label>Source IDs, eine pro Zeile</label><textarea name='source_ids' required></textarea><button>Reviewte Capsule + Agent Task anlegen</button></form></div><div class='card'><h2>Capsules & Request-Preflights</h2><table><thead><tr><th>Run</th><th>Typ</th><th>Status</th><th>Profil</th><th>Letzte Entscheidung</th><th>Aktion</th></tr></thead><tbody>{capsule_rows}</tbody></table></div>"
        return shell(body, case["title"])

    @app.get("/api/cases/{case_id}/ai/snapshot")
    def api_ai_snapshot(case_id: str, request: Request):
        require_case(request,case_id,"case.read"); ctx.cases.get_case(case_id)
        snap = ctx.build363.investigation_snapshot(case_id)
        return {"case_id": case_id, "counts": {k: len(v) for k, v in snap.items() if isinstance(v, list)}, "crawler": snap["crawler_monitor"], "go_active": bool(ctx.build363.active_investigation_go(case_id))}

    @app.get("/api/cases/{case_id}/ai/dossier")
    def api_ai_dossier(case_id: str, request: Request):
        require_case(request,case_id,"dossier.read"); ctx.cases.get_case(case_id)
        dossier = ctx.build363.latest_investigation_dossier(case_id)
        return dossier or {"case_id": case_id, "status": "not_generated", "hint": "Run AI investigation tick first"}

    @app.get("/api/cases/{case_id}/ai/crawler-monitor")
    def api_ai_crawler_monitor(case_id: str, request: Request):
        require_case(request,case_id,"crawler.monitor"); ctx.cases.get_case(case_id)
        return ctx.build363.monitor_investigation_crawler(case_id)

    @app.post("/cases/{case_id}/ai/intake")
    def ai_intake(case_id: str, request: Request, objective: str = Form(...), key_questions: str = Form(""), scope_notes: str = Form(""), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"dossier.write"); ctx.cases.get_case(case_id)
        questions = [x.strip() for x in key_questions.splitlines() if x.strip()]
        ctx.build363.create_investigation_intake(case_id=case_id, objective=objective, key_questions=questions, scope_notes=scope_notes)
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/ai/go")
    def ai_go(case_id: str, request: Request, go: str = Form(...), csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"voice.research"); ctx.cases.get_case(case_id)
        try:
            ctx.build363.start_investigation_go(case_id=case_id, go=go)
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return RedirectResponse(f"/cases/{case_id}", status_code=303)

    @app.post("/cases/{case_id}/ai/tick")
    def ai_tick(case_id: str, request: Request, csrf: str = Form(...)):
        require_csrf(request, csrf); require_case(request,case_id,"voice.research"); ctx.cases.get_case(case_id)
        ctx.build363.investigation_supervisor_tick(case_id=case_id)
        return RedirectResponse(f"/cases/{case_id}/ai/briefing", status_code=303)

    @app.get("/cases/{case_id}/ai/briefing")
    def ai_briefing(case_id: str, request: Request):
        require_case(request,case_id,"dossier.read"); case = ctx.cases.get_case(case_id)
        dossier = ctx.build363.latest_investigation_dossier(case_id)
        if not dossier:
            dossier = ctx.build363.build_investigation_dossier(case_id=case_id)
        facts = ''.join(f"<li>{_esc(x.get('statement',''))}</li>" for x in dossier.get('facts',[])[:20]) or "<li class='muted'>Noch keine reviewten Fakten.</li>"
        hyps = ''.join(f"<li>{_esc(x.get('statement',''))} <small>({float(x.get('confidence',0)):.2f})</small></li>" for x in dossier.get('hypotheses',[])[:20]) or "<li class='muted'>Noch keine Hypothesen.</li>"
        questions = ''.join(f"<li>{_esc(x)}</li>" for x in dossier.get('open_questions',[])[:20])
        body = f"<p><a href='/cases/{_esc(case_id)}'>← Fall</a></p><div class='card'><h1>AI-Ermittlungsbriefing</h1><p>{_esc(dossier.get('executive_summary',''))}</p><button id='eeSpeak'>Vorlesen</button> <button id='eeStop'>Stop</button><div id='eeSpeechText' hidden>{_esc(dossier.get('speech_text',''))}</div></div><div class='card'><h2>Reviewte Fakten</h2><ul>{facts}</ul></div><div class='card'><h2>Erste Hypothesen</h2><p class='muted'>AI-Kandidaten; menschliche Prüfung erforderlich.</p><ul>{hyps}</ul></div><div class='card'><h2>Offene Fragen</h2><ul>{questions}</ul></div><script src='/assets/build363.js'></script>"
        return shell(body, case['title'])

    @app.get("/api/cases/{case_id}/team")
    def api_case_team(case_id: str, request: Request):
        require_case(request,case_id,"case.read")
        return ctx.build363.team_status(case_id)

    @app.post("/api/team/users")
    async def api_team_create_user(request: Request):
        item=require_auth(request); body=await request.json()
        try:return ctx.build363.team_create_user(identity=item,username=str(body.get("username") or ""),display_name=str(body.get("display_name") or ""),global_role=str(body.get("global_role") or "investigator"),password=str(body.get("password") or ""))
        except Exception as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.post("/api/cases/{case_id}/team/assign")
    async def api_team_assign(case_id: str, request: Request):
        item=require_auth(request); body=await request.json()
        try:return ctx.build363.assign_case_role(identity=item,case_id=case_id,username=str(body.get("username") or ""),case_role=str(body.get("case_role") or "analyst"),notes=str(body.get("notes") or "Build 363 team assignment"))
        except Exception as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.post("/api/cases/{case_id}/team/revoke")
    async def api_team_revoke(case_id: str, request: Request):
        item=require_auth(request); body=await request.json()
        try:return ctx.build363.revoke_case_role(identity=item,case_id=case_id,username=str(body.get("username") or ""),case_role=str(body.get("case_role") or "analyst"),reason=str(body.get("reason") or ""))
        except Exception as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.get("/api/cases/{case_id}/crawler/ops")
    def api_crawler_ops(case_id: str, request: Request):
        item=require_auth(request)
        try:return ctx.build363.crawler_operational_snapshot(identity=item,case_id=case_id)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))

    @app.post("/api/cases/{case_id}/crawler/recover")
    async def api_crawler_recover(case_id: str, request: Request):
        item=require_auth(request)
        try:return ctx.build363.recover_expired_crawler_leases(identity=item,case_id=case_id)
        except PermissionError as exc:raise HTTPException(status_code=403,detail=str(exc))

    @app.post("/api/cases/{case_id}/dossier/export/request")
    async def api_export_request(case_id: str, request: Request):
        item=require_auth(request); body=await request.json()
        try:return ctx.build363.request_dossier_export(case_id=case_id,identity=item,export_format=str(body.get("format") or "json"),report_id=str(body.get("report_id") or ""))
        except (ValueError,PermissionError) as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.get("/api/dossier/export/{task_id}")
    def api_export_status(task_id: str, request: Request):
        item=require_auth(request)
        try:
            status=ctx.build363.export_status(task_id);require_case(request,status["case_id"],"dossier.read");return status
        except KeyError:raise HTTPException(status_code=404,detail="Export request not found")

    @app.post("/api/dossier/export/{task_id}/review")
    async def api_export_review(task_id: str, request: Request):
        item=require_auth(request); body=await request.json()
        try:return ctx.build363.review_dossier_export(task_id=task_id,identity=item,decision=str(body.get("decision") or ""),rationale=str(body.get("rationale") or ""))
        except (ValueError,PermissionError,KeyError) as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.post("/api/dossier/export/{task_id}/execute")
    async def api_export_execute(task_id: str, request: Request):
        item=require_auth(request)
        try:return ctx.build363.execute_dossier_export(task_id=task_id,identity=item)
        except (ValueError,PermissionError,KeyError) as exc:raise HTTPException(status_code=403 if isinstance(exc,PermissionError) else 400,detail=str(exc))

    @app.get("/api/build363/final-status")
    def api_build363_final_status(request: Request):
        require_auth(request)
        return ctx.build363.final_status()

    @app.get("/assets/build363.js")
    def build363_js():
        from fastapi.responses import Response
        js = r"""(()=>{
const speak=document.getElementById('eeSpeak'),stopSpeak=document.getElementById('eeStop'),speech=document.getElementById('eeSpeechText');
if(speak&&speech){speak.addEventListener('click',()=>{if(!('speechSynthesis' in window))return;window.speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(speech.textContent||'');u.lang='de-DE';u.rate=1.0;window.speechSynthesis.speak(u);});}
if(stopSpeak){stopSpeak.addEventListener('click',()=>{if('speechSynthesis' in window)window.speechSynthesis.cancel();});}
const start=document.getElementById('eePushToTalk'),stop=document.getElementById('eeStopTalk'),transcript=document.getElementById('eeVoiceTranscript'),mode=document.getElementById('eeVoiceMode'),interpret=document.getElementById('eeInterpretVoice'),summary=document.getElementById('eeIntentSummary'),confirmBox=document.getElementById('eeVoiceConfirm'),confirmBtn=document.getElementById('eeConfirmVoice'),status=document.getElementById('eeVoiceStatus');
let recorder=null,chunks=[],currentIntent=null;
async function postJSON(url,payload){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Request failed');return d;}
if(start){start.addEventListener('click',async()=>{try{if(!navigator.mediaDevices||!window.MediaRecorder)throw new Error('MediaRecorder nicht verfügbar');const stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=e=>{if(e.data&&e.data.size)chunks.push(e.data)};recorder.onstop=async()=>{stream.getTracks().forEach(t=>t.stop());const blob=new Blob(chunks,{type:recorder.mimeType||'audio/webm'});const form=new FormData();form.append('audio',blob,'push_to_talk.webm');form.append('mode',mode?mode.value:'command');form.append('human_started','true');try{status.textContent='Lokale Transkription läuft …';const caseId=interpret.dataset.case;const r=await fetch(`/api/cases/${caseId}/voice/transcribe`,{method:'POST',body:form});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Transkription fehlgeschlagen');if(d.transcript)transcript.value=d.transcript;status.textContent=d.status==='transcribed'?'Transkript lokal erstellt. Audio wurde nicht gespeichert.':'Lokales STT nicht verfügbar; bitte Transkript manuell eingeben.';if(d.intent_id){currentIntent=d;showIntent(d);}}catch(e){status.textContent=String(e.message||e);}};recorder.start();status.textContent='Aufnahme aktiv – Push-to-talk.';}catch(e){status.textContent=String(e.message||e);}});}
if(stop){stop.addEventListener('click',()=>{if(recorder&&recorder.state!=='inactive')recorder.stop();});}
function showIntent(d){currentIntent=d;summary.style.display='block';summary.textContent=`Intent: ${d.intent}. ${d.summary||d.intent_summary||''}`;confirmBox.style.display=d.requires_confirmation?'block':'none';}
if(interpret){interpret.addEventListener('click',async()=>{try{const d=await postJSON(`/api/cases/${interpret.dataset.case}/voice/propose`,{transcript:transcript.value,mode:mode?mode.value:'command'});showIntent(d);if(!d.requires_confirmation&&!d.manual_ui_required){const x=await postJSON(`/api/voice/${d.intent_id}/execute`,{confirmed:false,edited_transcript:transcript.value});summary.textContent+=` Status: ${x.state}.`;}}catch(e){status.textContent=String(e.message||e);}});}
if(confirmBtn){confirmBtn.addEventListener('click',async()=>{if(!currentIntent)return;try{const x=await postJSON(`/api/voice/${currentIntent.intent_id}/execute`,{confirmed:true,edited_transcript:transcript.value});summary.textContent=`Intent: ${currentIntent.intent}. Status: ${x.state}.`;confirmBox.style.display='none';}catch(e){status.textContent=String(e.message||e);}});}
})();"""
        return Response(content=js, media_type="application/javascript", headers={"Cache-Control":"no-store"})

    return app
