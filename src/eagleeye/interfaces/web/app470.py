"""Build 470: evidence-grounded readiness screen, not an unconditional product release."""
from __future__ import annotations
import hashlib
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from eagleeye.application.entity_registry461 import EntityRegistry461
from .app469 import create_workspace_app469
from .app448 import COOKIE
from .app449 import _drop

def create_workspace_app470(*, base_dir=None):
    app=create_workspace_app469(base_dir=base_dir,workspace_build="470.0")
    ctx=app.state.context
    app.version="470.0"
    app.title="EagleEye Build 470 – Investigation Checkpoint"
    registry=(Path(base_dir) if base_dir is not None else Path.home()/".eagleeye")/"entity_registry_462.sqlite3"
    _drop(app,"/health",{"GET"})

    @app.get("/health")
    def health470():
        integrity=bool(ctx.build458.build458_status().get("integrity_valid",False))
        return {"ok":True,"build":"470.0","status":"ok" if integrity else "hold",
                "integrity_valid":integrity,"production_release_ready":False,
                "next_checkpoint":"475.0"}

    @app.get("/readiness470",response_class=HTMLResponse)
    def readiness(request:Request,case_id:str=""):
        fingerprint=hashlib.sha256("|".join((request.headers.get("user-agent",""),
            request.headers.get("accept-language",""),
            request.client.host if request.client else "")).encode()).hexdigest()
        identity=ctx.team_identity_359.validate_session(
            request.cookies.get(COOKIE,""),client_fingerprint=fingerprint,touch=True)
        if not identity:
            return RedirectResponse("/security/login",status_code=303)
        selected=next((c for c in ctx.team_governance_359.visible_cases(identity)
                       if str(c.get("case_id"))==case_id),None)
        if selected is None:
            return RedirectResponse("/",status_code=303)
        documents=ctx.document_intelligence_458.documents(identity=identity,case_id=case_id)
        with EntityRegistry461(registry) as store:
            graph=store.graph(case_id)
        known={d["document_id"] for d in documents}
        references=[row["source_ref"] for rel in graph["relations"] for row in rel["sources"]]
        doc_refs=[r for r in references if r.startswith("doc458:")]
        resolved=sum(r[7:] in known for r in doc_refs)
        unresolved=len(references)-resolved
        stages=[
            ("Importierte Fall-Dokumente",str(len(documents)),"Ist-Bestand; Quellenqualität nicht bewertet"),
            ("Entitäten",str(len(graph["entities"])),"Fallbezogene Speicherung"),
            ("Beziehungen",str(len(graph["relations"])),"Ungeprüfte Hypothesen möglich"),
            ("Auflösbare Dokumentreferenzen",str(resolved),"Fallzuordnung, kein Beweis"),
            ("Nicht bestätigte/verwaiste Quellenreferenzen",str(unresolved),"Manuelle oder fehlende Referenzen prüfen"),
            ("Reale Produkt-Suchqualität","N/A","Bisher nur isolierte synthetische FTS5-Baseline"),
            ("Live-Verfügbarkeit der drei Quellen","N/A","CI verwendet simulierte Anbieterantworten"),
            ("Genehmigter Dossierexport und Restore","N/A","Nicht durch diesen End-to-End-Test nachgewiesen"),
            ("Produktivfreigabe","NEIN","Eine unabhängige Einsatzfreigabe fehlt"),
        ]
        rows="".join("<tr><th>"+escape(name)+"</th><td>"+escape(value)+"</td><td>"+escape(note)+"</td></tr>"
                     for name,value,note in stages)
        def link(endpoint,title):
            return '<a href="'+escape(endpoint+"?"+urlencode({"case_id":case_id}),quote=True)+'">'+escape(title)+'</a>'
        return HTMLResponse(
            '<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>EagleEye Build 470 · Qualitätsgate</title>'
            '<style>body{font:1rem system-ui;max-width:1050px;margin:2rem auto;padding:1rem;'
            'background:#102137;color:#eff7fb}a{color:#87e6d4}th,td{padding:.7rem;'
            'border:1px solid #71899f;text-align:left}table{border-collapse:collapse;width:100%}</style>'
            '</head><body><main><h1>Build 470 – Fallbasierte Qualitätsprüfung</h1>'
            '<p><strong>Kein Produktiveinsatz freigegeben.</strong> '
            'Die automatisierte Code-Regression ist getrennt in GitHub Actions nachzuweisen.</p>'
            '<p>Fall: '+escape(str(selected.get("title","Fall")))+'</p><nav>'
            +link("/documents458","Dokumente")+" · "+link("/collect469","Quellen erfassen")+" · "
            +link("/graph464","Graph")+" · "+link("/review465","Fallprüfung")+" · "
            +'<a href="/benchmark468">Benchmark</a></nav>'
            '<h2>Messbarer Ist-Bestand und offene Freigabegates</h2>'
            '<table><thead><tr><th>Kriterium</th><th>Status</th><th>Interpretation</th></tr></thead>'
            '<tbody>'+rows+'</tbody></table>'
            '<p>Bestandene Unit-Tests ersetzen keine eigenständige Praxiserprobung oder rechtliche Prüfung.</p>'
            '</main></body></html>',headers={"Cache-Control":"no-store"})
    return app

create_app=create_workspace_app470
