"""Case-scoped inventory and explicit limits; no production endorsement."""
from html import escape
from fastapi import Request
from fastapi.responses import HTMLResponse
from .operations476 import case_access,page
from .findings478 import notes_db,notes_for_case
from .report479 import source_states,review_history

def checkpoint_inventory(app,user,case_id):
    with notes_db(app) as db:
        notes=notes_for_case(app,case_id)
        for row in notes:review_history(db,row)
        states=source_states(app,user,case_id,notes)
        def count(state):
            return sum(row['review_state']==state and states[row['finding_id']]=='snapshot_match' for row in notes)
        return {'total':len(notes),'snapshot_match':sum(s=='snapshot_match' for s in states.values()),
            'changed_or_missing':sum(s!='snapshot_match' for s in states.values()),
            'reviewed_self':count('reviewed_self'),'reviewed_second_account':count('reviewed_second_account'),
            'unreviewed':sum(row['review_state']=='unreviewed' for row in notes),
            'needs_rework':sum(row['review_state']=='needs_rework' for row in notes),
            'rejected':sum(row['review_state']=='rejected' for row in notes),
            'claims_created_automatically':0,'production_release_ready':False}

def attach_checkpoint(app,build):
    @app.get('/workbench/checkpoint',response_class=HTMLResponse)
    def checkpoint(request:Request,case_id:str=''):
        user,case=case_access(app,request,case_id);ctx=app.state.context
        counts=checkpoint_inventory(app,user,case_id)
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        steps=[('Fall und Benutzerberechtigung','VORHANDEN',str(case.get('title') or '')),
            ('Importierte Dokumente',str(len(docs)),'Originale fallbezogen prüfen'),
            ('Quellengebundene Arbeitsbefunde',str(counts['total']),'Beobachtung, Hypothese, Gegenbeleg oder Unsicherheit'),
            ('Passende Original-Snapshots',str(counts['snapshot_match']),'Dateibytes, Dokument- und Anker-Hash sowie exaktes Zitat geprüft'),
            ('Geänderte oder fehlende Quellen',str(counts['changed_or_missing']),'Erneute Prüfung nötig'),
            ('Ungeprüfte Befunde',str(counts['unreviewed']),'Keine bestätigten Tatsachen'),
            ('Eigenprüfung bei passender Quelle',str(counts['reviewed_self']),'Keine unabhängige Freigabe'),
            ('Zweites Konto bei passender Quelle',str(counts['reviewed_second_account']),'Technische Kontotrennung; keine Garantie personeller Unabhängigkeit'),
            ('Überarbeitung / verworfen',str(counts['needs_rework'])+' / '+str(counts['rejected']),'Historie bleibt erhalten'),
            ('Markdown-Arbeitsbericht','VERFÜGBAR','Vollständiger Export oder explizite Größenablehnung; kein offizielles Dossier'),
            ('Bestehender formaler Dossierprozess','SEPARAT','Evidence → Claims → Vier-Augen-Review über die Expertenwerkzeuge'),
            ('Offline-Sicherung und Restore','WERKZEUGE VORHANDEN','Gesamten eigenen Arbeitsordner sichern; neuen Ordner und Originalstellen praktisch prüfen'),
            ('Live-Quellenabdeckung','BEGRENZT','Nur DNS A, RDAP .com, Crossref DOI; kein allgemeiner Crawler'),
            ('Reale Modell-, Such- und Entity-Resolution-Güte','NICHT NACHGEWIESEN','Synthetische Regression ist keine Feldmessung'),
            ('Unabhängige Sicherheits- und Einsatzabnahme','AUSSTEHEND','Technische CI und getrennte Testkonten ersetzen diese Abnahme nicht'),
            ('Produktionsreife','NEIN','Keine pauschale Einsatzfreigabe für sensible Aufträge')]
        table='<table><thead><tr><th>Arbeitsschritt</th><th>Ist</th><th>Einordnung</th></tr></thead><tbody>'
        table+=''.join('<tr><th>'+escape(label)+'</th><td>'+escape(value)+'</td><td>'+escape(note)+'</td></tr>' for label,value,note in steps)+'</tbody></table>'
        body='<p>Diese Übersicht liest den gespeicherten Fallbestand und seine Prüfhistorie. Sie bewertet keine vollständige Live-Recherche.</p>'+table
        return HTMLResponse(page('Operativer Prüfpunkt 480',case_id,body,build),headers={'Cache-Control':'no-store'})
