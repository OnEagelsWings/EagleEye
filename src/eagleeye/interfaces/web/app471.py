"""Build 471: browser-operated, persisted, source-cited local AI draft workflow."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import threading
from html import escape
from urllib.parse import urlencode, urlsplit

from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from eagleeye.application.assistant471 import Assistant471
from eagleeye.application.question472 import GAP_LABELS
from .app470 import create_workspace_app470
from .app448 import COOKIE
from .app449 import _drop
from .hypotheses473 import render_alternatives
from .review474 import render_review_matrix, read_assessments, render_assessment_history
from eagleeye.application.review474 import StaleDraftError


def create_workspace_app471(*, base_dir=None, workspace_build="471.0", questions_enabled=False, hypotheses_enabled=False, review_matrix_enabled=False, next_checkpoint="475.0"):
    app = create_workspace_app470(base_dir=base_dir, workspace_build=workspace_build)
    app.version = workspace_build
    app.title = "EagleEye Build " + workspace_build + " – Lokaler KI-Ermittler"
    ctx = app.state.context
    service = Assistant471(ctx)
    app.state.assistant471 = service
    secret = secrets.token_bytes(32)
    generation = threading.Lock()
    _drop(app, "/health", {"GET"})

    @app.get("/health")
    def health():
        valid = bool(ctx.build458.build458_status().get("integrity_valid", False))
        return {"ok": True, "build": workspace_build, "status": "ok" if valid else "hold",
                "integrity_valid": valid, "production_release_ready": False, "next_checkpoint": next_checkpoint}

    def identity(request, case_id):
        fp = hashlib.sha256("|".join((request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""), request.client.host if request.client else "")).encode()).hexdigest()
        user = ctx.team_identity_359.validate_session(request.cookies.get(COOKIE, ""), client_fingerprint=fp, touch=True)
        if not user:
            raise HTTPException(401, "Bitte anmelden.")
        try:
            service.authorize(user, case_id)
        except PermissionError as exc:
            raise HTTPException(403, "Kein Zugriff auf diesen Fall.") from exc
        return user

    def token(request, case_id):
        return hmac.new(secret, (request.cookies.get(COOKIE, "") + "|" + case_id).encode(), hashlib.sha256).hexdigest()

    async def submission(request):
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > 64000:
                raise HTTPException(413, "Formular ist zu groß.")
            data.extend(chunk)
        async def receive_form():
            return {"type": "http.request", "body": bytes(data), "more_body": False}
        form_request = Request(request.scope, receive=receive_form)
        form = await form_request.form(max_fields=64, max_files=0, max_part_size=8000)
        if len(form.multi_items()) > 64:
            raise HTTPException(413, "Zu viele Formularfelder.")
        case_id = str(form.get("case_id", ""))
        user = identity(request, case_id)
        if not hmac.compare_digest(str(form.get("csrf_token", "")), token(request, case_id)):
            raise HTTPException(403, "Ungültiges Formular; Seite neu öffnen.")
        origin = request.headers.get("origin", "")
        if origin and (urlsplit(origin).netloc != request.headers.get("host", "")
                       or urlsplit(origin).scheme not in {"http", "https"}):
            raise HTTPException(403, "Fremder Formularursprung gesperrt.")
        return form, case_id, user

    def error(exc):
        if isinstance(exc, StaleDraftError):
            raise HTTPException(409, "Quellenstand verändert oder beschädigt. Neuen Entwurf erzeugen oder diesen Entwurf verwerfen.") from exc
        if isinstance(exc, PermissionError):
            raise HTTPException(403, "Aktion für diesen Fall gesperrt.") from exc
        if isinstance(exc, ConnectionError):
            raise HTTPException(503, "Lokales Ollama nicht erreichbar. Ollama starten und ein lokal installiertes Modell verwenden. Kein Cloud-Fallback.") from exc
        raise HTTPException(422, "Entwurf nicht gespeichert. Eingaben, Belegintegrität oder Modellantwort prüfen. Nur lokale Modelle und exakt zitierte Fundstellen sind zulässig.") from exc

    @app.get("/assistant471", response_class=HTMLResponse)
    def page(request: Request, case_id: str = "", offset: int = Query(0, ge=0, le=100000)):
        user = identity(request, case_id)
        try:
            documents = service.documents.documents(identity=user, case_id=case_id)
            history = service.history(user, case_id, offset=offset)
        except (ValueError, PermissionError) as exc:
            error(exc)
        csrf = token(request, case_id)
        hidden = '<input type="hidden" name="case_id" value="'+escape(case_id, quote=True)+'"><input type="hidden" name="csrf_token" value="'+csrf+'">'
        hidden += '<input type="hidden" name="offset" value="'+str(offset)+'">'
        choices = ''.join('<label><input type="checkbox" name="document_id" value="'+escape(d['document_id'], quote=True)+'"> '+escape(d['title'])+' · '+escape(d['state'])+'</label>' for d in documents)
        question_form = ('<label>Arbeitsfrage (optional)<textarea name="question" maxlength="1000" rows="3"></textarea></label><p>Leer lassen für eine Zusammenfassung. Bei fehlenden Belegen muss die Antwort die Quellenlücke ausweisen.</p>' if questions_enabled else '')
        if hypotheses_enabled:
            question_form += '<label>Arbeitsweise <select name="analysis_mode"><option value="answer">Frage beantworten</option><option value="alternatives">Alternative Hypothesen und Gegenprüfung</option></select></label>'
        cards = ''
        for run in history:
            by_id = {s['anchor_id']: s for s in run['sources']}
            statements = ''
            for statement in run['summary']['statements']:
                citations = ''
                for citation in statement['citations']:
                    source = by_id[citation['anchor_id']]
                    url = '/documents458?' + urlencode({'case_id': case_id, 'document_id': source['document_id']}) + '#anchor-' + source['anchor_id']
                    citations += '<blockquote>'+escape(citation['quote'])+'</blockquote><p><a href="'+escape(url, quote=True)+'">'+escape(source['title'])+' · '+escape(source['locator'])+'</a></p><small>Beleg-SHA-256: '+escape(source['sha256'])+' · Erfasst: '+escape(source['captured_at'])+' · Extraktion: '+escape(source['extraction_state'])+'</small>'
                statements += '<li><p>'+escape(statement['text'])+'</p>'+citations+'</li>'
            question_text = ('<h4>Arbeitsfrage</h4><p>'+escape(run.get('question', ''))+'</p>' if run.get('question') else '')
            if run['summary'].get('answer_status') == 'insufficient_evidence':
                question_text += '<p><strong>Quellen reichen für eine Antwort nicht aus.</strong></p>'
            alternatives_html = render_alternatives(run, case_id)
            uncertainty = ''.join('<li>'+escape(x)+'</li>' for x in run['summary']['uncertainties'])
            uncertainty += ''.join('<li>'+escape(GAP_LABELS[code])+'</li>' for code in run['summary'].get('gap_reasons', []))
            review = ''
            if run['status'] == 'review_required':
                review = '<form method="post" action="/assistant471/review">'+hidden+'<input type="hidden" name="run_id" value="'+escape(run['run_id'], quote=True)+'">'+(render_review_matrix(run) if review_matrix_enabled else '')+'<label>Prüfentscheidung <select name="decision"><option value="acknowledged">Gelesen und geprüft – bleibt KI-Vorschlag</option><option value="rejected">Verwerfen</option></select></label><label>Begründung <textarea name="note" minlength="12" maxlength="2000" required></textarea></label><button>Prüfentscheidung speichern</button></form>'
            elif run['review']:
                review = '<p>Prüfung: '+escape(run['review']['by'])+' · '+escape(run['review']['at'])+'</p><p>'+escape(run['review']['note'])+'</p>'
                review += render_assessment_history(run)
                if review_matrix_enabled and run['status']=='acknowledged' and run['review'].get('assessments') is None:
                    review += '<p>Ältere Gesamtprüfung ohne Einzelbewertungen; für die neue Einzelprüfung einen neuen Entwurf erzeugen.</p>'
            cards += '<article id="'+escape(run['run_id'], quote=True)+'"><h3>KI-Vorschlag · '+escape(run['status'])+'</h3><p>'+escape(run['created_at'])+' · '+escape(run['model'])+'</p><small>Modell-Digest: '+escape(run['model_digest'])+'</small>'+question_text+'<ol>'+statements+'</ol>'+alternatives_html+'<h4>Unsicherheiten</h4><ul>'+uncertainty+'</ul><p>'+escape(run['coverage'])+' Fundstellen und Hashes zeigen den Stand bei Erstellung; spätere Änderungen benötigen einen neuen Entwurf.</p>'+review+'</article>'
        pagination = ''
        if offset:
            pagination += '<a href="'+escape('/assistant471?'+urlencode({'case_id':case_id,'offset':max(0,offset-20)}),quote=True)+'">← Neuere Entwürfe</a> '
        if len(history)==20 and offset+20<=100000:
            pagination += '<a href="'+escape('/assistant471?'+urlencode({'case_id':case_id,'offset':offset+20}),quote=True)+'">Ältere Entwürfe →</a>'
        home = '/?' + urlencode({'case_id': case_id})
        return HTMLResponse('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EagleEye · Lokaler KI-Ermittler</title><style>body{font:1rem system-ui;line-height:1.5;overflow-wrap:anywhere;max-width:980px;margin:auto;padding:1rem;background:#102137;color:#eff7fb}a{color:#8ee6d2}article,fieldset{border:1px solid #8aa0b8;border-radius:.5rem;padding:1rem;margin:1rem 0}label{display:block;margin:.7rem 0}input,select,button,textarea{font:inherit;max-width:100%;box-sizing:border-box;padding:.5rem}textarea{width:100%}small,blockquote{overflow-wrap:anywhere}button{cursor:pointer}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #f9cd73}</style></head><body><main><nav><a href="'+escape(home, quote=True)+'">← Fallübersicht</a></nav><h1>Lokaler KI-Ermittler</h1><p>Quellengebundene Zusammenfassung als <strong>ungeprüfter Vorschlag</strong>. Zitate werden technisch zugeordnet; ob sie die Aussage tragen, prüfst du am Original. Keine automatische Faktenbestätigung.</p><p>Ollama läuft auf diesem Computer (127.0.0.1:11434). Verwende ein bereits installiertes lokales Modell, beispielsweise mistral:latest. Die Funktion lädt kein Modell herunter.</p><form method="post" action="/assistant471/generate">'+hidden+'<fieldset><legend>Ein bis drei Fall-Dokumente wählen</legend>'+(choices or '<p>Zuerst Fall-Dokumente mit Quellen-URL importieren.</p>')+'</fieldset>'+question_form+'<label>Installiertes Ollama-Modell <input name="model" value="mistral:latest" maxlength="120" required></label><p>Auswahl: maximal vier Textfundstellen pro Dokument, jeweils bis zu 1500 Zeichen. Keine vollständige Dokumentanalyse. Quelleninhalte werden als unvertrauenswürdige Daten verarbeitet. Lauf kann bis zu zwei Minuten dauern.</p><button>Auswahl lokal zusammenfassen</button></form><h2>Gespeicherte Entwürfe und Prüfungen</h2><p>20 Entwürfe je Seite; ältere Entwürfe über die Seitennavigation. Eine Prüfbestätigung erzeugt keine bestätigten Claims.</p>'+cards+'<nav>'+pagination+'</nav></main></body></html>', headers={"Cache-Control": "no-store"})

    @app.post("/assistant471/generate")
    async def generate(request: Request):
        form, case_id, user = await submission(request)
        if not generation.acquire(blocking=False):
            raise HTTPException(429, "Ein lokaler KI-Lauf ist bereits aktiv.")
        try:
            def work():
                try:
                    with ctx.audit.actor_scope(user['username']):
                        return service.generate(user, case_id, [str(x) for x in form.getlist('document_id')], str(form.get('model', '')), question=str(form.get('question', '')) if questions_enabled else '', analysis_mode=str(form.get('analysis_mode', 'answer')) if hypotheses_enabled else 'answer')
                finally:
                    # Disconnecting the HTTP client must not free a still-running model slot.
                    generation.release()
            run = await asyncio.shield(asyncio.to_thread(work))
        except (PermissionError, ValueError, ConnectionError, KeyError, TypeError) as exc:
            error(exc)
        return RedirectResponse('/assistant471?' + urlencode({'case_id': case_id}) + '#' + run['run_id'], status_code=303)

    @app.post("/assistant471/review")
    async def review(request: Request):
        form, case_id, user = await submission(request)
        try:
            with ctx.audit.actor_scope(user['username']):
                service.review(user, case_id, str(form.get('run_id', '')), str(form.get('decision', '')), str(form.get('note', '')), assessments=read_assessments(form), require_assessments=review_matrix_enabled)
        except (ValueError, PermissionError) as exc:
            if isinstance(exc, ValueError) and not isinstance(exc, StaleDraftError):
                raise HTTPException(422, "Prüfung nicht gespeichert. Erforderliche Einzelbewertungen und Begründungen prüfen; der Entwurf muss noch ungeprüft sein.") from exc
            error(exc)
        return RedirectResponse('/assistant471?' + urlencode({'case_id': case_id, 'offset': min(100000,max(0,int(str(form.get('offset', '0'))) if len(str(form.get('offset', '0')))<=6 and str(form.get('offset', '0')).isdecimal() else 0))}), status_code=303)

    return app


create_app = create_workspace_app471
