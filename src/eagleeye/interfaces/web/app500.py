"""EagleEye Internal 500 candidate: integrated workflow plus visible readiness screen."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse
from .app499 import create_workspace_app499
from .operations476 import case_access, page

def create_workspace_app500(*,base_dir=None,workspace_build="500.0"):
    app=create_workspace_app499(base_dir=base_dir,workspace_build=workspace_build)
    app.version=workspace_build
    app.title="EagleEye Internal 1.0 – Build "+workspace_build
    app.state.internal_candidate500=True
    ctx=app.state.context

    @app.get("/workbench/release500",response_class=HTMLResponse)
    def readiness(request:Request,case_id:str=""):
        user,_case=case_access(app,request,case_id)
        plan_count=ctx.db.one("SELECT count(*) AS n FROM case_plans_496 WHERE case_id=?",(case_id,))["n"]
        provider_count=len(ctx.provider_collection_120.list_providers())
        body=(
            '<p><strong>Build 500 – Internal Release Candidate.</strong> '
            'Einheitliche Fallakte, kontrollierte PersonOSINT-Aufnahme, WARC/Dokumente, '
            'KI-Planvorschläge, Provider-Engine und unbestätigte Graph-Übernahme.</p>'
            '<p class="warn">Kein automatischer Produktivstatus. '
            'Freigabe erfordert realen Windows-Installations-/Neustarttest,'
            ' vollständigen Restore, Datenschutz- und OPSEC-Prüfung sowie'
            ' Nutzung ausschließlich zulässiger Quellen.</p>'
            '<table><tr><th>Prüfkriterium</th><th>Stand</th></tr>'
            '<tr><td>Laufzeitversion</td><td>'+escape(str(workspace_build))+'</td></tr>'
            '<tr><td>Fallbezogene Recherchepläne</td><td>'+str(plan_count)+'</td></tr>'
            '<tr><td>Registrierte kontrollierte Provider</td><td>'+str(provider_count)+'</td></tr>'
            '<tr><td>WARC-Quellensicherung</td><td>Vorhanden, Freigabe erforderlich</td></tr>'
            '<tr><td>Lokale KI-Vorschläge</td><td>Optional; nur mit Ollama, manuelle Bestätigung</td></tr>'
            '<tr><td>Live-Zugriffe</td><td>Nur eigenständig genehmigte Suchanfragen</td></tr>'
            '<tr><td>Automatische Identitätsbestätigung</td><td>Deaktiviert</td></tr>'
            '<tr><td>Interne Einsatzfreigabe</td><td>OFFEN – Release Candidate</td></tr></table>')
        return HTMLResponse(page("EagleEye Internal 500 – Bereitschaft",case_id,body,workspace_build),
                            headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})
    from .public_sources501 import attach_public_sources501
    attach_public_sources501(app, workspace_build)
    return app

create_app=create_workspace_app500
