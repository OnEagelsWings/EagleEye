"""Build 463: link graph relationships to REAL case-authorized imported documents."""
from __future__ import annotations
import hashlib
from html import escape
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from eagleeye.application.entity_registry461 import EntityRegistry461
from .app462 import create_workspace_app462
from .app448 import COOKIE
from .app449 import _drop

def create_workspace_app463(*, base_dir=None, workspace_build="463.0", workspace_title="Evidence-linked Entity Intelligence"):
    app = create_workspace_app462(base_dir=base_dir, workspace_build=workspace_build, workspace_title=workspace_title)
    ctx = app.state.context
    registry_path = (Path(base_dir) if base_dir is not None else Path.home()/".eagleeye")/"entity_registry_462.sqlite3"
    _drop(app,"/health",{"GET"})
    @app.get("/health")
    def health():
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,"next_checkpoint":"465.0"}
    def actor(request,case_id):
        fingerprint=hashlib.sha256("|".join((request.headers.get("user-agent",""),
                     request.headers.get("accept-language",""),
                     request.client.host if request.client else "")).encode()).hexdigest()
        ident=ctx.team_identity_359.validate_session(request.cookies.get(COOKIE,""),
                       client_fingerprint=fingerprint,touch=True)
        if not ident:
            return None,RedirectResponse("/security/bootstrap" if ctx.team_identity_359.bootstrap_required()
                                         else "/security/login",status_code=303)
        if not any(str(c.get("case_id"))==case_id for c in ctx.team_governance_359.visible_cases(ident)):
            return None,RedirectResponse("/",status_code=303)
        return ident,None
    @app.get("/source-links463",response_class=HTMLResponse)
    def documents(request:Request,case_id:str=""):
        identity,redirect=actor(request,case_id)
        if redirect is not None:return redirect
        docs=ctx.document_intelligence_458.documents(identity=identity,case_id=case_id)
        with EntityRegistry461(registry_path) as store:graph=store.graph(case_id)
        opts="".join('<option value="'+escape(e["id"],quote=True)+'">'+escape(e["label"])+'</option>'
                     for e in graph["entities"])
        sources="".join('<option value="'+escape(d["document_id"],quote=True)+'">'+escape(d["title"])+'</option>'
                        for d in docs)
        links="".join('<li><a href="/documents458?'+escape(urlencode({"case_id":case_id,"document_id":d["document_id"]}),quote=True)+'">'+escape(d["title"])+'</a></li>' for d in docs)
        return HTMLResponse('<!doctype html><html lang="de"><head><meta charset="utf-8"><title>EagleEye '+escape(workspace_build)+'</title>'
           '<style>body{font:1rem system-ui;max-width:60rem;margin:2rem auto;padding:1rem;background:#0d1a29;color:#f1f6fd}'
           'a{color:#76dcca}select,input,button{padding:.7rem;margin:.4rem}</style></head><body><main>'
           '<p><a href="/entities462?'+escape(urlencode({"case_id":case_id}),quote=True)+'">← Zurück zu Entitäten</a></p>'
           '<h1>Beziehungen mit importierten Dokumenten verknüpfen</h1><p>Ein Dokument ist ein überprüfbarer Fundort, keine bestätigte Tatsache.</p>'
           '<h2>Dokumente dieses Falls</h2><ul>'+links+'</ul>'
           '<form method="post" action="/source-links463/create">'
           '<input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'">'
           '<label>Von <select name="source_id">'+opts+'</select></label>'
           '<label>Zu <select name="target_id">'+opts+'</select></label>'
           '<label>Beziehung <input name="predicate" maxlength="128" required></label>'
           '<label>Importiertes Dokument <select name="document_id">'+sources+'</select></label>'
           '<button type="submit">Quellengebundene Hypothese anlegen</button></form></main></body></html>',
           headers={"Cache-Control":"no-store"})
    @app.post("/source-links463/create")
    async def create(request:Request):
        data=await request.form()
        case_id=str(data.get("case_id",""))
        ident,redirect=actor(request,case_id)
        if redirect is not None:return redirect
        origin=request.headers.get("origin","")
        if origin and (urlsplit(origin).netloc!=request.headers.get("host","") or urlsplit(origin).scheme not in {"http","https"}):
            raise HTTPException(status_code=403,detail="Cross-origin request")
        document_id=str(data.get("document_id",""))
        docs=ctx.document_intelligence_458.documents(identity=ident,case_id=case_id)
        if not any(d["document_id"]==document_id for d in docs):
            raise HTTPException(status_code=422,detail="Document must be imported into this case")
        try:
            with EntityRegistry461(registry_path) as store:
                store.create_relation(case_id=case_id,source_id=str(data.get("source_id","")),
                    target_id=str(data.get("target_id","")),predicate=str(data.get("predicate","")),
                    source_refs=["doc458:"+document_id])
        except ValueError as exc:
            raise HTTPException(status_code=422,detail=str(exc)) from exc
        return RedirectResponse("/entities462?"+urlencode({"case_id":case_id,"message":"relation_saved"}),status_code=303)
    return app

create_app=create_workspace_app463
