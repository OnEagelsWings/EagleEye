"""Build 464: case-scoped clickable relationship network and source drill-down."""
from __future__ import annotations

import hashlib
import math
from html import escape
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from eagleeye.application.entity_registry461 import EntityRegistry461, RELATION_STATES
from .app463 import create_workspace_app463
from .app448 import COOKIE
from .app449 import _drop

def create_workspace_app464(*, base_dir=None, workspace_build="464.0",
                            workspace_title="Interactive Evidence Network"):
    app = create_workspace_app463(base_dir=base_dir, workspace_build=workspace_build,
                                  workspace_title=workspace_title)
    ctx = app.state.context
    db_path = (Path(base_dir) if base_dir is not None else Path.home()/".eagleeye")/"entity_registry_462.sqlite3"
    _drop(app,"/health",{"GET"})

    @app.get("/health")
    def health():
        integrity = bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":workspace_build,"status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,
                "next_checkpoint":"465.0"}

    @app.get("/graph464", response_class=HTMLResponse)
    def interactive_graph(request:Request,case_id:str="",focus:str="",state:str="all"):
        fingerprint=hashlib.sha256("|".join((
            request.headers.get("user-agent",""),
            request.headers.get("accept-language",""),
            request.client.host if request.client else "",
        )).encode()).hexdigest()
        ident=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),client_fingerprint=fingerprint,touch=True
        )
        if not ident:
            return RedirectResponse("/security/bootstrap" if ctx.team_identity_359.bootstrap_required()
                                    else "/security/login",status_code=303)
        case = next((v for v in ctx.team_governance_359.visible_cases(ident)
                     if str(v.get("case_id"))==case_id),None)
        if case is None:
            return RedirectResponse("/",status_code=303)
        with EntityRegistry461(db_path) as store:
            graph=store.graph(case_id)
        docs=ctx.document_intelligence_458.documents(identity=ident,case_id=case_id)
        documents={d["document_id"]:d for d in docs}
        state = state if state in RELATION_STATES else "all"
        nodes=graph["entities"][:80]
        allowed={n["id"] for n in nodes}
        edges=[r for r in graph["relations"]
               if r["source_id"] in allowed and r["target_id"] in allowed
               and (state=="all" or r["state"]==state)][:200]
        by_id={n["id"]:n for n in nodes}
        positions={}
        count=max(1,len(nodes))
        for i,n in enumerate(nodes):
            angle=math.tau*i/count - math.pi/2
            positions[n["id"]]=(round(460+340*math.cos(angle),2),
                                round(330+245*math.sin(angle),2))
        def target(item_id):
            return "/graph464?"+urlencode({"case_id":case_id,"focus":item_id,"state":state})
        lines=[]
        for e in edges:
            x1,y1=positions[e["source_id"]]
            x2,y2=positions[e["target_id"]]
            lines.append('<a href="'+escape(target(e["id"]),quote=True)+'" aria-label="Beziehung '+escape(e["predicate"],quote=True)+'">'
                '<title>'+escape(by_id[e["source_id"]]["label"]+" → "+e["predicate"]+" → "+by_id[e["target_id"]]["label"])+'</title>'
                '<line x1="'+str(x1)+'" y1="'+str(y1)+'" x2="'+str(x2)+'" y2="'+str(y2)+'" '
                'stroke="'+("#f0c36b" if e["state"]=="hypothesis" else "#7dd5c1")+'" '
                'stroke-width="'+("5" if focus==e["id"] else "2")+'"/></a>')
        colors={"person":"#82b7fc","company":"#eeb981","organization":"#bca5ff",
                "place":"#8bd9ae","event":"#f4a5b4","document":"#e5d588"}
        circles=[]
        for node in nodes:
            x,y=positions[node["id"]]
            label=node["label"][:23]
            circles.append('<a href="'+escape(target(node["id"]),quote=True)+'" role="link" '
                 'aria-label="'+escape(node["kind"]+": "+node["label"],quote=True)+'">'
                 '<title>'+escape(node["label"]+" ("+node["kind"]+")")+'</title>'
                 '<circle cx="'+str(x)+'" cy="'+str(y)+'" r="'+("27" if focus==node["id"] else "22")+'" '
                 'stroke="#f7fafc" stroke-width="2" fill="'+colors.get(node["kind"],"#c7d3e4")+'"/>'
                 '<text x="'+str(x)+'" y="'+str(y+39)+'" text-anchor="middle" fill="#f4f7ff" font-size="13">'
                 +escape(label)+'</text></a>')
        selected=next((n for n in nodes if n["id"]==focus),None)
        chosen=next((e for e in edges if e["id"]==focus),None)
        details=""
        if selected:
            details="<h2>Entität: "+escape(selected["label"])+"</h2><p>Typ: "+escape(selected["kind"])+"</p><p>"+escape(selected["notes"])+"</p>"
        if chosen:
            details="<h2>Beziehung: "+escape(chosen["predicate"])+"</h2><p>Status: "+escape(chosen["state"])+"</p>"
            details+="<p>"+escape(by_id[chosen["source_id"]]["label"])+" → "+escape(by_id[chosen["target_id"]]["label"])+"</p>"
            details+="<h3>Quellenverweise (kein automatischer Wahrheitsnachweis)</h3><ul>"
            for source in chosen["sources"]:
                ref=source["source_ref"]
                if ref.startswith("doc458:") and ref[7:] in documents:
                    d=documents[ref[7:]]
                    link="/documents458?"+urlencode({"case_id":case_id,"document_id":d["document_id"]})
                    details+='<li><a href="'+escape(link,quote=True)+'">'+escape(d["title"])+'</a> – tatsächlicher Fall-Import, inhaltlich ungeprüft</li>'
                else:
                    details+="<li>"+escape(ref)+" – manueller Quellenverweis, nicht verifiziert</li>"
            details+="</ul>"
        if not details:
            details="<h2>Auswahl</h2><p>Knoten oder Verbindung anklicken, um Details und Quellen zu sehen.</p>"
        filters=" ".join('<a href="'+escape("/graph464?"+urlencode({"case_id":case_id,"state":s}),quote=True)+'">'+escape(s)+'</a>'
                         for s in ("all","hypothesis","supported","disputed","rejected"))
        rows="".join('<li><a href="'+escape(target(e["id"]),quote=True)+'">'
             +escape(by_id[e["source_id"]]["label"]+" → "+e["predicate"]+" → "+by_id[e["target_id"]]["label"])
             +'</a> ('+escape(e["state"])+')</li>' for e in edges)
        home="/entities462?"+urlencode({"case_id":case_id})
        dossier="/?"+urlencode({"case_id":case_id,"view":"dossier"})
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye '+escape(workspace_build)+' · Intelligence Graph</title>'
            '<style>body{font:1rem system-ui;max-width:1100px;margin:1.3rem auto;padding:1rem;'
            'background:#0c1829;color:#f0f6ff}a{color:#83dfd0;margin-right:1rem}'
            'a:focus-visible{outline:3px solid white}svg{width:100%;height:auto;background:#13233a;'
            'border:1px solid #41546a;border-radius:12px}svg a:hover circle{stroke:#ffee8a;stroke-width:5}'
            '.panel{padding:1rem;background:#172a3e;border-radius:10px;margin:1rem 0}</style>'
            '</head><body><main><nav><a href="'+escape(home,quote=True)+'">← Entitäten</a>'
            '<a href="'+escape(dossier,quote=True)+'">Dossier</a></nav>'
            '<h1>Intelligence Graph · Build '+escape(workspace_build)+'</h1>'
            '<p>Fall: '+escape(str(case.get("title","")))+' · '+str(len(nodes))+' Knoten / '
            +str(len(edges))+' sichtbare Beziehungen</p><p>Filter: '+filters+'</p>'
            '<svg viewBox="0 0 920 700" xmlns="http://www.w3.org/2000/svg" role="img" '
            'aria-label="Anklickbarer Beziehungsgraph">'+''.join(lines)+''.join(circles)+'</svg>'
            '<section class="panel">'+details+'</section><section class="panel"><h2>Barrierefreie Beziehungsliste</h2><ul>'+rows+'</ul></section>'
            '<p>Maximal 80 Knoten und 200 Beziehungen pro Ansicht. Beziehungen sind Hypothesen, solange nicht gesondert geprüft.</p>'
            '</main></body></html>',headers={"Cache-Control":"no-store"})
    return app

create_app=create_workspace_app464
