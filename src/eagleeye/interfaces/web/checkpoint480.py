"""Build 480: honest per-case operational readiness screen, not a production gate."""
from __future__ import annotations
from html import escape
from urllib.parse import urlencode
from fastapi import Request
from fastapi.responses import HTMLResponse
from .operations476 import case_access, page
from .findings478 import notes_for_case
from .report479 import source_state

def attach_checkpoint(app,build):
    ctx=app.state.context
    @app.get("/workbench/checkpoint",response_class=HTMLResponse)
    def checkpoint(request:Request,case_id:str=""):
        user,case=case_access(app,request,case_id)
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        notes=notes_for_case(app,case_id)
        status=[source_state(app,user,case_id,row) for row in notes]
        sound=sum(1 for s in status if s=="snapshot_match")
        stale=len(status)-sound
        reviewed=sum(1 for r,s in zip(notes,status)
                     if r["review_state"]=="reviewed_self" and s=="snapshot_match")
        steps=[
            ("Fall und Benutzerberechtigung","VORHANDEN","Operativer Fall: "+str(case.get("title") or "")),
            ("Importierte Dokumente",str(len(docs)),"Originale nur fallbezogen abrufbar"),
            ("Quellengebundene Notizen",str(len(notes)),"Menschliche Beobachtungen und Hypothesen"),
            ("Integrität der zitierten Quellen",str(sound),"Passender Dokument-Hash und Originaltextanker"),
            ("Quellenänderungen / fehlende Belege",str(stale),"Erneute manuelle Prüfung nötig"),
            ("Begründete Eigenprüfungen",str(reviewed),"Keine unabhängige Freigabe"),
            ("Markdown-Arbeitsbericht","VERFÜGBAR","Nur mit Fallberechtigung abrufbar"),
            ("Reale Such- und Entity-Resolution-Güte","NICHT NACHGEWIESEN","Keine Feldleistung aus synthetischen Tests"),
            ("Unabhängige Sicherheitsprüfung / vollständiger Restore","AUSSTEHEND","Keine sensiblen Live-Aufträge"),
            ("Offizielle Dossierfreigabe / Produktionsreife","NEIN","Vier-Augen-Freigabe fehlt"),
        ]
        table="<table><thead><tr><th>Arbeitsschritt</th><th>Ist</th><th>Einordnung</th></tr></thead><tbody>"
        table+="".join("<tr><th>"+escape(label)+"</th><td>"+escape(value)+"</td><td>"+escape(note)+"</td></tr>"
                       for label,value,note in steps)+"</tbody></table>"
        link="/workbench/report?"+urlencode({"case_id":case_id})
        body=('<p>Diese Statusseite wertet den gespeicherten Fallbestand aus, '
              'nicht die Qualität einer vollständigen Live-Recherche.</p>'+table+
              '<p><a href="'+escape(link,quote=True)+'">Quellenkritischen Arbeitsbericht öffnen →</a></p>'
              '<p><strong>Nächste Schritte:</strong> Gegenbelege suchen, unabhängig prüfen, '
              'Vier-Augen-Freigabe und Wiederherstellung praktisch abnehmen.</p>')
        return HTMLResponse(page("Operativer Prüfpunkt 480",case_id,body,build),
                            headers={"Cache-Control":"no-store"})
