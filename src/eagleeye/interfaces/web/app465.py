"""Build 465: case-scoped synthesis preview; approved exports remain governed by the existing dossier workflow."""
from __future__ import annotations
import hashlib
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application.entity_registry461 import EntityRegistry461
from .app464 import create_workspace_app464
from .app448 import COOKIE
from .app449 import _drop

def create_workspace_app465(*,base_dir=None,workspace_build="465.0",workspace_title="Integrated Investigation Checkpoint"):
    app=create_workspace_app464(base_dir=base_dir,workspace_build=workspace_build,
                                 workspace_title=workspace_title)
    ctx=app.state.context
    db_path=(Path(base_dir) if base_dir is not None else Path.home()/".eagleeye")/"entity_registry_462.sqlite3"
    _drop(app,"/health",{"GET"})

    @app.get("/health")
    def health465():
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,
                "next_checkpoint":"470.0"}

    @app.get("/review465",response_class=HTMLResponse)
    def case_summary(request:Request,case_id:str=""):
        fingerprint=hashlib.sha256("|".join((
            request.headers.get("user-agent",""),request.headers.get("accept-language",""),
            request.client.host if request.client else "")).encode()).hexdigest()
        identity=ctx.team_identity_359.validate_session(request.cookies.get(COOKIE,""),
                       client_fingerprint=fingerprint,touch=True)
        if not identity:
            return RedirectResponse("/security/bootstrap" if ctx.team_identity_359.bootstrap_required()
                                     else "/security/login",status_code=303)
        selected=next((c for c in ctx.team_governance_359.visible_cases(identity)
                       if str(c.get("case_id"))==case_id),None)
        if selected is None:
            return RedirectResponse("/",status_code=303)
        with EntityRegistry461(db_path) as store:
            graph=store.graph(case_id)
        docs=ctx.document_intelligence_458.documents(identity=identity,case_id=case_id)
        by_doc={d["document_id"]:d for d in docs}
        by_entity={e["id"]:e for e in graph["entities"]}
        def url(base,**kw):
            return base+"?"+urlencode({"case_id":case_id,**kw})
        def link(href,title):
            return '<a href="'+escape(href,quote=True)+'">'+escape(title)+'</a>'
        documents="".join('<li>'+link(url("/documents458",document_id=d["document_id"]),d["title"])
                         +' · '+escape(d.get("state","unreviewed"))+'</li>' for d in docs)
        nodes="".join('<li>'+escape(e["label"])+' ('+escape(e["kind"])+')</li>'
                      for e in graph["entities"])
        verified_refs=0
        broken_refs=0
        rows=[]
        for rel in graph["relations"]:
            references=[]
            for s in rel["sources"]:
                ref=s["source_ref"]
                if ref.startswith("doc458:") and ref[7:] in by_doc:
                    d=by_doc[ref[7:]]
                    references.append(link(url("/documents458",document_id=d["document_id"]),d["title"])
                                      +' (importiert, Inhalt nicht automatisch bestätigt)')
                    verified_refs+=1
                else:
                    references.append(escape(ref)+' (manuell oder nicht mehr auflösbar)')
                    broken_refs+=1
            source=by_entity.get(rel["source_id"],{}).get("label","?")
            target=by_entity.get(rel["target_id"],{}).get("label","?")
            rows.append('<li>'+escape(source+' → '+rel["predicate"]+' → '+target)
                        +' · <strong>'+escape(rel["state"])+'</strong> · '+", ".join(references)+'</li>')
        risk="CHECK" if broken_refs or any(r["state"]!="supported" for r in graph["relations"]) else "REVIEW"
        # This view is explicitly NOT an export. Existing four-eyes review/export routes remain authoritative.
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye 465 · Fallprüfung</title>'
            '<style>body{font:1rem system-ui;max-width:65rem;margin:2rem auto;padding:1rem;background:#101c2c;color:#eff6ff}'
            'a{color:#79ddc9}section{padding:1rem;border:1px solid #556b80;border-radius:10px;margin:1rem 0}'
            '.caution{color:#ffd8a0}a:focus-visible{outline:3px solid #fff}</style></head><body><main>'
            '<nav>'+link(url("/"),"Fallübersicht")+" · "+link(url("/graph464"),"Netzwerkgraph")+" · "
            +link(url("/source-links463"),"Dokumentbelege")+" · "+link(url("/",view="dossier"),"Dossier und Freigaben")+'</nav>'
            '<h1>Integrierte Fallprüfung · Build 465</h1><h2>'+escape(selected.get("title","Fall"))+'</h2>'
            '<p class="caution"><strong>Ungeprüfte Arbeitsansicht · Status '+risk+'</strong>. '
            'Dies ist keine Feststellung von Tatsachen, keine Freigabe und kein Dossierexport. '
            'Der verbindliche Export erfolgt nur über den vorhandenen Dossier-/Vier-Augen-Prozess.</p>'
            '<section><h3>Quellen ('+str(len(docs))+')</h3><ul>'+documents+'</ul></section>'
            '<section><h3>Entitäten ('+str(len(graph["entities"]))+')</h3><ul>'+nodes+'</ul></section>'
            '<section><h3>Beziehungen ('+str(len(rows))+')</h3><ul>'+''.join(rows)+'</ul></section>'
            '<section><h3>Belegprüfung</h3><p>Importierte Fall-Dokumentverweise: '+str(verified_refs)
            +' · Manuelle/nicht auflösbare Verweise: '+str(broken_refs)
            +'</p><p>Die Existenz eines Dokumentes bestätigt nicht automatisch die darin enthaltene Behauptung.</p></section>'
            '</main></body></html>',
            headers={"Cache-Control":"no-store"},
        )
    return app

create_app=create_workspace_app465
