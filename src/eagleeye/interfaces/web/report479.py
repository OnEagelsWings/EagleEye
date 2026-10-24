"""Human source review and literal, non-official working reports."""
from __future__ import annotations
import hashlib,json,secrets
from datetime import datetime,timezone
from html import escape
from urllib.parse import urlencode
from fastapi import HTTPException,Request,Query
from fastapi.responses import HTMLResponse,RedirectResponse,Response
from .operations476 import case_access,page
from .app364 import CSRF_COOKIE
from .findings478 import (notes_db,notes_for_case,verify_post,bounded_form,
    checked_note,finding_hash,KINDS,get_anchor)

REVIEW_COLUMNS=('review_id','case_id','finding_id','reviewed_by','reviewed_at',
    'decision','reason','source_state','before_hash','after_hash','previous_hash')

def review_hash(row):
    return hashlib.sha256(json.dumps({k:row[k] for k in REVIEW_COLUMNS},
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def init_reviews(app):
    with notes_db(app) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS operational_finding_reviews_479(
            review_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,finding_id TEXT NOT NULL,
            reviewed_by TEXT NOT NULL,reviewed_at TEXT NOT NULL,decision TEXT NOT NULL,
            reason TEXT NOT NULL,source_state TEXT NOT NULL,before_hash TEXT NOT NULL,
            after_hash TEXT NOT NULL,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL)""")
        db.execute('CREATE INDEX IF NOT EXISTS finding_review_479_idx ON operational_finding_reviews_479(case_id,finding_id)')

def review_history(db,row):
    entries=db.all('SELECT * FROM operational_finding_reviews_479 WHERE case_id=? AND finding_id=? ORDER BY rowid',
        (row['case_id'],row['finding_id']))
    previous='GENESIS';after=None
    for entry in entries:
        if entry['previous_hash']!=previous or entry['record_hash']!=review_hash(entry) or (after and entry['before_hash']!=after):
            raise HTTPException(409,'Integrität der Prüfhistorie verletzt.')
        previous=entry['record_hash'];after=entry['after_hash']
    if (after and after!=row['record_hash']) or (not entries and row['review_state']!='unreviewed'):
        raise HTTPException(409,'Prüfstand und Historie stimmen nicht überein.')
    return entries

def source_states(app,user,case_id,notes):
    """Hash each original file once per response, retaining per-anchor verification."""
    service=app.state.context.document_intelligence_458
    documents={};result={}
    for row in notes:
        key=row['document_id']
        try:
            if key not in documents:
                service._identity(user,case_id,'case.read',key)
                doc=service._document(key)
                valid=(doc['case_id']==case_id and doc['state']!='extraction_rejected'
                    and doc['record_hash']==service._rh(doc) and service._payload_current(doc))
                documents[key]=(doc,valid)
            doc,valid=documents[key];anchor=service._anchor(row['anchor_id'])
            same=(valid and anchor['case_id']==case_id and anchor['document_id']==key
                and anchor['record_hash']==service._rh(anchor)
                and anchor['document_sha256']==doc['document_sha256']==row['document_sha256']
                and anchor['text_excerpt']==row['source_excerpt'] and doc['source_url']==row['source_url']
                and (anchor['record_hash']==row['anchor_hash'] or (row['legacy_imported'] and not row['anchor_hash'])))
            result[row['finding_id']]='snapshot_match' if same else 'changed'
        except (KeyError,ValueError,HTTPException,PermissionError,OSError):
            result[row['finding_id']]='missing'
    return result

def source_state(app,user,case_id,row):
    return source_states(app,user,case_id,[row])[row['finding_id']]

def literal(value):
    # Imported Markdown/HTML and remote image syntax must remain inert.
    return '\n'.join('    '+line for line in str(value).splitlines()) or '    (leer)'

def report_body(app,user,case,notes):
    states=source_states(app,user,str(case['case_id']),notes)
    lines=['# EagleEye – Quellengebundener Arbeitsbericht','',
        '**KEIN freigegebenes Ermittlungsdossier oder bestätigter Tatsachenbericht.**',
        'Zitate beweisen keine Interpretation. Eigenprüfung und Prüfung durch ein zweites Konto ersetzen keine offizielle Freigabe.','']
    for label,key in [('Fall','title'),('Auftrag/Zweck','purpose'),('Rechtsgrundlage','legal_basis')]:
        lines.extend([label+':','',literal(case.get(key) or 'im Fall prüfen'),''])
    lines.extend(['Vollständig enthaltene Arbeitsbefunde: '+str(len(notes)),''])
    with notes_db(app) as db:
        for index,row in enumerate(notes,1):
            history=review_history(db,row)
            lines.extend(['## Arbeitsbefund '+str(index),''])
            fields=[('Kurzbezeichnung',row['title']),('Einordnung',KINDS.get(row['kind'],'Arbeitsnotiz')),
                ('Eigene Interpretation',row['interpretation']),('Originaltextauszug',row['source_excerpt']),
                ('Dokument-ID',row['document_id']),('Anker-ID',row['anchor_id']),
                ('Dokument SHA-256 bei Aufnahme',row['document_sha256']),
                ('Anker-Snapshot',row['anchor_hash']),('Herkunfts-URL (unbestätigte Metadaten)',row['source_url']),
                ('Quellenintegrität beim Export',states[row['finding_id']]),
                ('Prüfstatus',row['review_state']),('Prüfbegründung',row['review_reason']),
                ('Prüfendes Konto',row['reviewed_by']),('Verfasst von',row['created_by']),
                ('Verfasst am',row['created_at']),('Befund-Hash',row['record_hash'])]
            for label,value in fields:lines.extend([label+':','',literal(value),''])
            lines.extend(['Prüfhistorie:',''])
            for entry in history:
                lines.extend([literal(entry['reviewed_at']+' | '+entry['reviewed_by']+' | '+entry['decision']),
                    literal(entry['reason']),literal('Historien-Hash: '+entry['record_hash']),''])
    lines.extend(['## Ausstehende Prüfung','',
        '- Gegenbelege, alternative Erklärungen und unabhängige Quellen prüfen.',
        '- Vier-Augen-Freigabe und offizieller Dossierexport erfolgen nicht über diesen Arbeitsbericht.',
        '- Hashes erkennen Änderungen; sie bestätigen keine inhaltliche Wahrheit.',''])
    return '\n'.join(lines)

def attach_report(app,build):
    ctx=app.state.context;init_reviews(app)
    @app.get('/workbench/report',response_class=HTMLResponse)
    def report_view(request:Request,case_id:str='',offset:int=Query(0,ge=0,le=100000)):
        user,case=case_access(app,request,case_id)
        with notes_db(app) as db:
            total=db.one('SELECT COUNT(*) AS n FROM operational_findings_478 WHERE case_id=?',(case_id,))['n']
            offset=min(offset,((max(1,total)-1)//50)*50);offset=(offset//50)*50
            rows=notes_for_case(app,case_id,offset=offset,limit=50)
            histories={row['finding_id']:review_history(db,row) for row in rows}
        states=source_states(app,user,case_id,rows)
        allowed='source.review' in ctx.team_governance_359.effective_capabilities(user,case_id)
        token=escape(request.cookies.get(CSRF_COOKIE,''),quote=True);cards=[]
        for row in rows:
            state=states[row['finding_id']];form=''
            if allowed:
                form='<form method="post" action="/workbench/report/review">'
                for name,value in [('case_id',case_id),('finding_id',row['finding_id']),('expected_hash',row['record_hash']),('csrf',request.cookies.get(CSRF_COOKIE,''))]:
                    form+='<input type="hidden" name="'+name+'" value="'+escape(value,quote=True)+'">'
                form+=('<label>Prüfentscheidung<select name="decision"><option value="reviewed">Quelle geprüft</option>'
                    '<option value="needs_rework">Überarbeitung nötig</option><option value="rejected">Verwerfen</option></select></label>'
                    '<label>Begründete Prüfung (keine offizielle Freigabe)<textarea name="reason" required minlength="10" maxlength="1200" rows="3"></textarea></label>'
                    '<button>Prüfentscheidung speichern</button></form>')
            history=''.join('<li>'+escape(h['reviewed_at']+' · '+h['reviewed_by']+' · '+h['decision'])+'<p>'+escape(h['reason'])+'</p></li>' for h in histories[row['finding_id']])
            original='/documents458?'+urlencode({'case_id':case_id,'document_id':row['document_id'],'anchor_id':row['anchor_id']})
            cards.append('<section class="card"><h2>'+escape(row['title'])+'</h2><p>'+escape(row['interpretation'])+
                '</p><p>Quellenstand: '+escape(state)+' · Status: '+escape(row['review_state'])+
                '</p><blockquote>'+escape(row['source_excerpt'])+'</blockquote><a href="'+escape(original,quote=True)+
                '">Originalfundstelle öffnen</a><p>Prüfendes Konto: '+escape(row['reviewed_by'])+' · '+escape(row['review_reason'])+
                '</p><details><summary>Prüfhistorie</summary><ol>'+history+'</ol></details>'+form+'</section>')
        nav=''
        for value,label in [(offset-50,'Neuere Arbeitsbefunde'),(offset+50,'Ältere Arbeitsbefunde')]:
            if 0<=value<total:nav+='<a href="'+escape('/workbench/report?'+urlencode({'case_id':case_id,'offset':value}),quote=True)+'">'+label+'</a> '
        link='/workbench/report.md?'+urlencode({'case_id':case_id})
        body=('<p>Fall '+escape(str(case.get('title') or ''))+' · '+str(total)+' Arbeitsbefunde insgesamt. Bis zu 50 je Seite.</p>'
            '<p>Eigenprüfung und Prüfung durch ein zweites Konto sind getrennt sichtbar. Keine automatische Tatsachenaufwertung.</p>'
            '<p><a href="'+escape(link,quote=True)+'">Arbeitsbericht als Markdown herunterladen →</a></p>'
            +(''.join(cards) or '<p>Bitte zuerst quellengebundene Arbeitsbefunde speichern.</p>')+'<p>'+nav+'</p>')
        return HTMLResponse(page('Prüfen und Arbeitsbericht erstellen',case_id,body,build),headers={'Cache-Control':'no-store'})

    @app.post('/workbench/report/review')
    async def human_review(request:Request):
        form=await bounded_form(request,max_bytes=24000);case_id=str(form.get('case_id',''))
        user,_=case_access(app,request,case_id,'source.review')
        verify_post(app,request,user,form.get('csrf',''))
        reason=str(form.get('reason','')).strip();decision=str(form.get('decision','reviewed'))
        if not 10<=len(reason)<=1200 or decision not in {'reviewed','needs_rework','rejected'}:
            raise HTTPException(422,'Prüfentscheidung und Begründung (10–1200 Zeichen) prüfen.')
        note_id=str(form.get('finding_id',''));expected=str(form.get('expected_hash',''))
        with notes_db(app) as db:
            ctx.document_intelligence_458._identity(user,case_id,'source.review',note_id)
            raw=db.one('SELECT * FROM operational_findings_478 WHERE finding_id=? AND case_id=?',(note_id,case_id))
            if not raw:raise HTTPException(404,'Befund in diesem Fall nicht vorhanden.')
            row=checked_note(raw);history=review_history(db,row)
            if expected!=row['record_hash']:raise HTTPException(409,'Der Befund wurde inzwischen geändert. Bitte neu laden.')
            state=source_state(app,user,case_id,row)
            if decision=='reviewed':
                if state!='snapshot_match':raise HTTPException(409,'Quelle geändert oder fehlt. Neu prüfen oder verwerfen.')
                doc,_,anchor=get_anchor(ctx,user,case_id,row['document_id'],row['anchor_id'])
                if (doc['document_sha256']!=row['document_sha256'] or doc['source_url']!=row['source_url'] or anchor['text_excerpt']!=row['source_excerpt'] or (row['anchor_hash'] and anchor['record_hash']!=row['anchor_hash'])):
                    raise HTTPException(409,'Quelle wurde während der Prüfung verändert.')
                row['anchor_hash']=anchor['record_hash'];row['legacy_imported']=0
                row['review_state']='reviewed_self' if user['username']==row['created_by'] else 'reviewed_second_account'
            else:row['review_state']=decision
            before=row['record_hash'];row['review_reason']=reason;row['reviewed_by']=user['username']
            row['record_hash']=finding_hash(row)
            entry=dict(review_id=secrets.token_hex(16),case_id=case_id,finding_id=note_id,
                reviewed_by=user['username'],reviewed_at=datetime.now(timezone.utc).isoformat(),
                decision=decision,reason=reason,source_state=state,before_hash=before,after_hash=row['record_hash'],
                previous_hash=history[-1]['record_hash'] if history else 'GENESIS')
            entry['record_hash']=review_hash(entry)
            db.execute('UPDATE operational_findings_478 SET review_state=?,review_reason=?,reviewed_by=?,anchor_hash=?,legacy_imported=?,record_hash=? WHERE finding_id=? AND case_id=?',
                (row['review_state'],reason,row['reviewed_by'],row['anchor_hash'],row['legacy_imported'],row['record_hash'],note_id,case_id))
            db.execute('INSERT INTO operational_finding_reviews_479 VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                tuple(entry[k] for k in REVIEW_COLUMNS+('record_hash',)))
            ctx.audit.log('human_finding_reviewed_479','finding',note_id,case_id,
                {'actor':user['username'],'decision':decision,'state':row['review_state'],'review_hash':entry['record_hash'],'claims_created':0})
        return RedirectResponse('/workbench/report?'+urlencode({'case_id':case_id}),status_code=303)

    @app.get('/workbench/report.md')
    def download_report(request:Request,case_id:str=''):
        user,case=case_access(app,request,case_id)
        with notes_db(app) as db:
            count=db.one('SELECT COUNT(*) AS n FROM operational_findings_478 WHERE case_id=?',(case_id,))['n']
            if count>1000:raise HTTPException(413,'Mehr als 1000 Befunde: vollständiger Einzelbericht zu groß. Keine Notizen wurden abgeschnitten.')
            md=report_body(app,user,case,notes_for_case(app,case_id))
        if len(md.encode())>20*1024*1024:raise HTTPException(413,'Vollständiger Arbeitsbericht überschreitet 20 MiB.')
        safe_id=''.join(ch for ch in case_id if ch.isalnum() or ch in '-_')[:60] or 'fall'
        return Response(md,media_type='text/markdown; charset=utf-8',
            headers={'Content-Disposition':'attachment; filename="EagleEye_'+safe_id+'_Arbeitsbericht.md"',
                'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.get('/workbench/recovery',response_class=HTMLResponse)
    def recovery_help(request:Request,case_id:str=''):
        case_access(app,request,case_id)
        body=('<p>Die Offline-Sicherung enthält den <strong>gesamten Arbeitsordner mit allen Fällen</strong>, '
            'Benutzerkonten, Originaldateien, Notizen, Berichten und lokalen Datenbanken. Sie ist kein fallbezogener Export.</p>'
            '<ol><li>Serverfenster vollständig schließen.</li><li><strong>EAGLEEYE_SICHERUNG.bat</strong> öffnen; neue ZIP-Datei außerhalb des Arbeitsordners wählen.</li>'
            '<li>Nur eine eigene vertrauenswürdige Sicherung über <strong>EAGLEEYE_WIEDERHERSTELLEN.bat</strong> auswählen. '
            'Ein neuer Arbeitsordner wird angelegt; bestehende Ordner werden nicht überschrieben.</li>'
            '<li>START_EAGLEEYE_PRO.bat öffnen, neu anmelden und Fall/Originalstellen kontrollieren.</li></ol>'
            '<p>Die Sicherung ist unverschlüsselt. An einem eigenen geschützten Ort aufbewahren. Datei-Hashes prüfen Übertragungsintegrität, '
            'nicht die Echtheit eines fremden Archivs. Bestehende Sitzungen werden beim Restore widerrufen; die Datenbank ändert sich dadurch '
            'erst nach vollständiger Dateiprüfung. Der Beleg steht in restore-receipt.json.</p>')
        return HTMLResponse(page('Sicherung und Wiederherstellung',case_id,body,build),headers={'Cache-Control':'no-store'})
