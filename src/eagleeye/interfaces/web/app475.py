"""Build 475: case-scoped AI readiness, without a production release claim."""
import hashlib
from html import escape
from urllib.parse import urlencode
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from eagleeye.application.checkpoint475 import review_inventory
from .app471 import create_workspace_app471
from .app448 import COOKIE


def create_workspace_app475(*,base_dir=None,workspace_build='475.0'):
    app=create_workspace_app471(base_dir=base_dir,workspace_build=workspace_build,questions_enabled=True,
        hypotheses_enabled=True,review_matrix_enabled=True,next_checkpoint='480.0')
    ctx=app.state.context;service=app.state.assistant471

    @app.get('/ai-checkpoint475',response_class=HTMLResponse)
    def checkpoint(request:Request,case_id:str=''):
        fp=hashlib.sha256('|'.join((request.headers.get('user-agent',''),
            request.headers.get('accept-language',''),request.client.host if request.client else '')).encode()).hexdigest()
        identity=ctx.team_identity_359.validate_session(request.cookies.get(COOKIE,''),client_fingerprint=fp,touch=True)
        if not identity:raise HTTPException(401,'Bitte anmelden.')
        try:counts=review_inventory(service,identity,case_id)
        except PermissionError as exc:raise HTTPException(403,'Kein Zugriff auf diesen Fall.') from exc
        except ValueError as exc:raise HTTPException(409,'Prüfbestand nicht vollständig verifizierbar.') from exc
        metrics=[('Gespeicherte KI-Entwürfe',counts['total']),('Einzelprüfung ausstehend',counts['review_required']),
            ('Gelesen und beurteilt',counts['acknowledged']),('Davon mit vollständigen Einzelurteilen',counts['complete_item_reviews']),
            ('Ältere Gesamtprüfungen ohne Einzelurteile',counts['acknowledged_without_item_reviews']),('Verworfen',counts['rejected']),
            ('Reale Modellqualität und Halluzinationsrate','N/A'),('Semantische Folgerichtigkeit automatisch belegt','NEIN'),
            ('Modelllaufzeit auf Zielgerät','N/A'),('Live-Quellenqualität und unabhängige Einsatzprüfung','N/A'),
            ('Freigegebener Dossierexport und Restore','N/A')]
        rows=''.join('<tr><th>'+escape(label)+'</th><td>'+escape(str(value))+'</td></tr>' for label,value in metrics)
        url=escape('/assistant471?'+urlencode({'case_id':case_id}),quote=True)
        legacy=escape('/readiness470?'+urlencode({'case_id':case_id}),quote=True)
        return HTMLResponse('<!doctype html><html lang="de"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>KI-Prüfpunkt 475</title>'
            '<style>body{font:1rem system-ui;max-width:1000px;margin:1rem auto;padding:1rem;background:#102137;color:#eff7fb}'
            'a{color:#87e6d4}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{padding:.7rem;border:1px solid #71899f;'
            'text-align:left;overflow-wrap:anywhere}th{width:70%}</style></head><body><main><h1>KI-Prüfpunkt 475</h1>'
            '<p><strong>Keine Produktivfreigabe.</strong> Ein gültiges Zitat beweist nicht die Aussage. '
            'Auch geprüfte Entwürfe bleiben Vorschläge und erzeugen keine Fakten oder Identitätszusammenführungen.</p>'
            '<nav><a href="'+url+'">Lokaler KI-Ermittler</a> · <a href="'+legacy+'">Weitere Freigabegates</a></nav>'
            '<h2>Aktueller Fallbestand</h2><table><tbody>'+rows+'</tbody></table>'
            '<p>Die Bestandszahlen lesen die gespeicherten, integritätsgeprüften Entwürfe dieses Falls. '
            'Sie sind keine Messung der Antwortqualität. Automatisierte Regression, Browserprüfung und '
            'deterministische Antwortregeln sind separat in den CI-Protokollen nachzuweisen.</p>'
            '<p>Nächster Prüfpunkt: Build 480.</p></main></body></html>',headers={'Cache-Control':'no-store'})
    return app

create_app=create_workspace_app475
