"""Build 469: authenticated operator-controlled collection into the existing case document store."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import secrets
import threading
import time
from html import escape
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from .app468 import create_workspace_app468
from .app448 import COOKIE
from .app449 import _drop
from eagleeye.application.collectors469 import PROVIDERS, collect


def create_workspace_app469(*, base_dir=None, workspace_build="469.0"):
    app=create_workspace_app468(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title="EagleEye Build "+workspace_build+" – Public Source Collection"
    ctx=app.state.context
    _drop(app,"/health",{"GET"})
    secret=secrets.token_bytes(32)
    limiter={}
    lock=threading.Lock()

    @app.get("/health")
    def health469():
        valid=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if valid else "hold",
                "integrity_valid":valid,"production_release_ready":False,"next_checkpoint":"470.0"}

    def current_actor(request:Request, case_id:str):
        fp=hashlib.sha256("|".join((request.headers.get("user-agent",""),
            request.headers.get("accept-language",""),
            request.client.host if request.client else "")).encode()).hexdigest()
        ident=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),client_fingerprint=fp,touch=True)
        if not ident:
            return None,RedirectResponse("/security/login",status_code=303)
        if not any(str(c.get("case_id"))==case_id for c in ctx.team_governance_359.visible_cases(ident)):
            return None,RedirectResponse("/",status_code=303)
        return ident,None

    def token(request,case_id):
        message=(str(request.cookies.get(COOKIE,""))+"|"+case_id).encode()
        return hmac.new(secret,message,hashlib.sha256).hexdigest()

    @app.get("/collect469",response_class=HTMLResponse)
    def collection_page(request:Request,case_id:str=""):
        ident,denied=current_actor(request,case_id)
        if denied is not None:return denied
        options="".join('<option value="'+escape(key,quote=True)+'">'+escape(label)+'</option>'
                        for key,label in PROVIDERS.items())
        back="/documents458?"+urlencode({"case_id":case_id})
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye '+escape(workspace_build)+' · Quellenimport</title>'
            '<style>body{max-width:850px;margin:2rem auto;padding:1rem;font:1rem system-ui;'
            'background:#132238;color:#f5f7fc}a{color:#8de7d7}'
            'input,select,button{font:inherit;padding:.6rem;margin:.4rem}'
            'label{display:block}</style></head><body><main>'
            '<p><a href="'+escape(back,quote=True)+'">← Fall-Dokumente</a></p>'
            '<h1>Öffentliche Quellen erfassen</h1>'
            '<p>Abfragen gehen an externe Anbieter. KEINE persönlichen, vertraulichen oder '
            'geschützten Rechercheindikatoren eingeben. Der Abruf liefert unbestätigte '
            'öffentliche Metadaten, keine belastbare Identitätsfeststellung.</p>'
            '<form method="post" action="/collect469/import">'
            '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
            '<input type="hidden" name="csrf_token" value="'+token(request,case_id)+'">'
            '<label>Quelle <select name="provider" required>'+options+'</select></label>'
            '<label>Domain oder DOI <input name="indicator" maxlength="256" required></label>'
            '<button type="submit">Metadaten abrufen und in diesen Fall importieren</button></form>'
            '<p>Verfügbarkeit der Drittanbieter nicht garantiert. 3 Abrufe pro Minute pro Sitzung.</p>'
            '</main></body></html>',headers={"Cache-Control":"no-store"})

    @app.post("/collect469/import")
    async def collect_into_case(request:Request):
        form=await request.form()
        case_id=str(form.get("case_id",""))
        identity,denied=current_actor(request,case_id)
        if denied is not None:return denied
        if not hmac.compare_digest(str(form.get("csrf_token","")),token(request,case_id)):
            raise HTTPException(status_code=403,detail="Invalid submission token")
        origin=request.headers.get("origin","")
        if origin and (urlsplit(origin).netloc!=request.headers.get("host","")
                       or urlsplit(origin).scheme not in {"http","https"}):
            raise HTTPException(status_code=403,detail="Cross-origin submission denied")
        provider=str(form.get("provider",""))
        indicator=str(form.get("indicator",""))
        if provider not in PROVIDERS:
            raise HTTPException(status_code=422,detail="Unsupported source")
        ident=str(identity.get("user_id") or identity.get("username"))
        now=time.monotonic()
        with lock:
            recent=[t for t in limiter.get(ident,[]) if now-t<60]
            if len(recent)>=3:
                raise HTTPException(status_code=429,detail="Source collection rate limit")
            limiter[ident]=recent+[now]
        try:
            packet=await asyncio.to_thread(collect,provider,indicator)
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502,detail="Public provider unavailable") from exc
        document=ctx.document_intelligence_458.import_bytes(
            identity=identity,case_id=case_id,filename=packet["filename"],
            raw=packet["raw"],title=packet["title"],source_url=packet["source_url"])
        return RedirectResponse("/documents458?"+urlencode({
            "case_id":case_id,"document_id":document["document_id"]}),status_code=303)
    return app

create_app=create_workspace_app469
