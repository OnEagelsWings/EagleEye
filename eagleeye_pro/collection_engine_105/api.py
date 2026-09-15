from __future__ import annotations

import html
import secrets
from pathlib import Path
from typing import Any

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from eagleeye_pro.core_recomposition_104_1.api import create_app as create_core_app

from .models import BrowserCaptureRequestModel, CollectionJobRequestModel


def create_app(*, base_dir: str | Path | None = None):
    app = create_core_app(base_dir=base_dir)

    async def require_local(request: Request, x_eagleeye_token: str = Header(default=""), ee_session: str = Cookie(default="")) -> str:
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            raise HTTPException(status_code=403, detail="Loopback access only")
        supplied = x_eagleeye_token or ee_session or request.query_params.get("token", "")
        if not secrets.compare_digest(supplied, app.state.local_token):
            raise HTTPException(status_code=403, detail="Local session token required")
        return supplied

    def context():
        from eagleeye_pro.core.app_context import AppContext
        ctx = AppContext(base_dir=Path(app.state.base_dir))
        try:
            yield ctx
        finally:
            ctx.close()

    @app.get("/collection", response_class=HTMLResponse)
    def collection_ui(response: Response, _: str = Depends(require_local), ctx=Depends(context)) -> str:
        response.set_cookie("ee_session", app.state.local_token, httponly=True, samesite="strict")
        cases = ctx.platform_103_1.list_cases()
        options = "".join(f"<option value='{html.escape(c['case_id'])}'>{html.escape(c.get('title',''))}</option>" for c in cases)
        readiness = ctx.collection_engine_105.readiness()
        readiness_text = html.escape(__import__('json').dumps(readiness, ensure_ascii=False, indent=2))
        return f"""<!doctype html><html lang='de'><head><meta charset='utf-8'><title>EagleEye Collection 105</title>
<style>body{{font-family:system-ui;max-width:1180px;margin:30px auto;padding:0 20px;background:#f3f6f9}}.card{{background:white;padding:18px;border-radius:10px;margin:12px 0}}label{{display:block;font-weight:650;margin-top:10px}}input,select,textarea,button{{width:100%;box-sizing:border-box;padding:9px;margin-top:5px}}button{{cursor:pointer;font-weight:700}}pre{{background:#101820;color:#e9f0f6;padding:12px;border-radius:7px;overflow:auto}}.warn{{border-left:5px solid #c77b00}}</style></head><body>
<h1>Collection Engine 105</h1><div class='card'><h2>Readiness</h2><pre>{readiness_text}</pre></div><div class='card warn'><b>Grenzen:</b> ausschließlich öffentliche Quellen. Kein Login-, CAPTCHA-, Paywall- oder Private-Account-Bypass. Öffentliche Profile gehorchen robots.txt; maximale öffentliche Reichweite bleibt rate-limited und fallgebunden.</div>
<div class='card'><h2>Crawl starten</h2><label>Fall</label><select id='case'>{options}</select><label>Engine</label><select id='engine'><option value='scrapy'>Scrapy Crawl</option><option value='playwright'>Playwright Browser Capture</option></select><label>Profil</label><select id='profile'><option value='focused'>Focused</option><option value='extended_public'>Extended Public</option><option value='maximum_public' selected>Maximum Public</option></select><label>Seed-URLs (eine pro Zeile)</label><textarea id='seeds' rows='5' placeholder='https://example.org/'></textarea><label>Titel</label><input id='title' value='Public collection'><label><input id='confirm' type='checkbox' style='width:auto'/> Ich bestätige die öffentliche Live-Erhebung und den freigegebenen Legal Scope.</label><button onclick='startJob()'>Job anlegen und starten</button></div>
<div class='card'><h2>Jobs</h2><button onclick='loadJobs()'>Aktualisieren</button><pre id='output'>Noch keine Abfrage.</pre></div>
<script>
async function api(path, options={{}}){{const r=await fetch(path,{{...options,headers:{{'Content-Type':'application/json',...(options.headers||{{}})}}}});const t=await r.text();if(!r.ok)throw new Error(r.status+' '+t);return t?JSON.parse(t):{{}};}}
function policy(profile){{const map={{focused:{{max_pages:150,max_depth:3,max_runtime_seconds:900,max_total_bytes:262144000,concurrent_requests:3,concurrent_requests_per_domain:1,download_delay_seconds:1.0,autothrottle_target_concurrency:0.75,browser_scroll_steps:10}},extended_public:{{max_pages:2500,max_depth:8,max_runtime_seconds:7200,max_total_bytes:2147483648,concurrent_requests:8,concurrent_requests_per_domain:2,download_delay_seconds:0.35,autothrottle_target_concurrency:1.5,browser_scroll_steps:18}},maximum_public:{{max_pages:10000,max_depth:12,max_runtime_seconds:21600,max_total_bytes:5368709120,max_response_bytes:36700160,concurrent_requests:12,concurrent_requests_per_domain:3,download_delay_seconds:0.20,autothrottle_target_concurrency:2.0,retry_times:3,max_query_variants_per_path:25,browser_scroll_steps:32}}}};return {{profile,...map[profile],explicit_scope_confirmation:true}};}}
async function startJob(){{try{{if(!document.getElementById('confirm').checked)throw new Error('Bestätigung fehlt');const seeds=document.getElementById('seeds').value.split(/\n+/).map(x=>x.trim()).filter(Boolean);const payload={{case_id:document.getElementById('case').value,engine:document.getElementById('engine').value,seed_urls:seeds,policy:policy(document.getElementById('profile').value),title:document.getElementById('title').value,explicit_live_confirmation:true}};const job=await api('/api/collection/jobs',{{method:'POST',body:JSON.stringify(payload)}});const started=await api('/api/collection/jobs/'+job.job_id+'/start',{{method:'POST',body:JSON.stringify({{explicit_live_confirmation:true}})}});document.getElementById('output').textContent=JSON.stringify(started,null,2);setTimeout(loadJobs,1000);}}catch(e){{document.getElementById('output').textContent=String(e);}}}}
async function loadJobs(){{try{{const cid=document.getElementById('case').value;const out=await api('/api/collection/jobs?case_id='+encodeURIComponent(cid));document.getElementById('output').textContent=JSON.stringify(out,null,2);}}catch(e){{document.getElementById('output').textContent=String(e);}}}}
</script></body></html>"""

    @app.get("/api/collection/profiles")
    def profiles(_: str = Depends(require_local), ctx=Depends(context)) -> list[dict[str, Any]]:
        return ctx.collection_engine_105.profiles()

    @app.get("/api/collection/readiness")
    def readiness(_: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.collection_engine_105.readiness()

    @app.get("/api/collection/jobs")
    def jobs(case_id: str = "", _: str = Depends(require_local), ctx=Depends(context)) -> list[dict[str, Any]]:
        return ctx.collection_engine_105.list_jobs(case_id)

    @app.post("/api/collection/jobs")
    def create_job(payload: CollectionJobRequestModel, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.collection_engine_105.create_job(payload)

    @app.get("/api/collection/jobs/{job_id}")
    def get_job(job_id: str, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.collection_engine_105.get_job(job_id)

    @app.post("/api/collection/jobs/{job_id}/start")
    def start_job(job_id: str, payload: dict[str, Any], _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        if not payload.get("explicit_live_confirmation"):
            raise HTTPException(status_code=400, detail="explicit_live_confirmation required")
        return ctx.collection_engine_105.start_background(job_id)

    @app.post("/api/collection/jobs/{job_id}/run")
    def run_job(job_id: str, payload: dict[str, Any], _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        if not payload.get("explicit_live_confirmation"):
            raise HTTPException(status_code=400, detail="explicit_live_confirmation required")
        return ctx.collection_engine_105.execute_job(job_id)

    @app.post("/api/collection/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.collection_engine_105.cancel_job(job_id)

    @app.post("/api/collection/browser-capture")
    def browser_capture(payload: BrowserCaptureRequestModel, _: str = Depends(require_local), ctx=Depends(context)) -> dict[str, Any]:
        return ctx.collection_engine_105.capture_browser(payload)

    return app
