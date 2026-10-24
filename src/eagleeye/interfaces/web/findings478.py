"""Investigator-authored source-bound notes, stored with the canonical case database."""
from __future__ import annotations
import hashlib,hmac,json,secrets,sqlite3
from contextlib import contextmanager
from datetime import datetime,timezone
from html import escape
from pathlib import Path
from urllib.parse import urlencode,urlsplit
from fastapi import HTTPException,Request,Query
from fastapi.responses import HTMLResponse,RedirectResponse
from .operations476 import case_access,page
from .app364 import CSRF_COOKIE

KINDS={'research_note':'Arbeitsnotiz','observation':'Beobachtung','hypothesis':'Hypothese',
       'counterevidence':'Gegenbeleg','uncertainty':'Unsicherheit / offene Frage'}
BASE_COLUMNS=('finding_id','case_id','document_id','anchor_id','title','interpretation',
    'source_excerpt','document_sha256','source_url','created_by','created_at',
    'review_state','review_reason','reviewed_by','kind','anchor_hash','legacy_imported')

INSERT_FINDING_SQL="""INSERT INTO operational_findings_478(
    finding_id,case_id,document_id,anchor_id,title,interpretation,source_excerpt,
    document_sha256,source_url,created_by,created_at,review_state,review_reason,
    reviewed_by,kind,anchor_hash,legacy_imported,record_hash)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


def finding_hash(row):
    return hashlib.sha256(json.dumps({k:row[k] for k in BASE_COLUMNS},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _import_old_notes(app,db):
    marker=db.one("SELECT * FROM operational_note_migrations_478 WHERE migration='sidecar_v1'")
    if marker:return
    legacy=Path(app.state.context.base_dir).resolve()/'data/operational_notes_478.sqlite3'
    if not legacy.is_file():return
    if legacy.stat().st_size>128*1024*1024:raise HTTPException(409,'Ältere Notizdatei ist zu groß für die automatische Übernahme.')
    old=sqlite3.connect(legacy.as_uri()+'?mode=ro',uri=True);old.row_factory=sqlite3.Row
    try:
        rows=old.execute('SELECT * FROM operational_findings_478 LIMIT 100001').fetchall()
    finally:old.close()
    if len(rows)>100000:raise HTTPException(409,'Ältere Notizen benötigen eine gesonderte Übernahme.')
    imported=skipped=0
    for old_row in rows:
        row=dict(old_row)
        try:app.state.context.cases.get_case(str(row['case_id']))
        except (KeyError,ValueError):skipped+=1;continue
        row={k:str(row.get(k) or '') for k in BASE_COLUMNS}
        row.update(review_state='unreviewed',review_reason='Aus älterem Arbeitsstand übernommen; erneut prüfen.',
            reviewed_by='',kind='research_note',anchor_hash='',legacy_imported=1)
        if not (4<=len(row['title'])<=180 and 10<=len(row['interpretation'])<=2400 and len(row['source_excerpt'])<=6000 and len(row['source_url'])<=4000):skipped+=1;continue
        row['record_hash']=finding_hash(row)
        columns=BASE_COLUMNS+('record_hash',)
        result=db.execute(INSERT_FINDING_SQL.replace('INSERT INTO','INSERT OR IGNORE INTO',1),
            tuple(row[k] for k in columns))
        imported+=result.rowcount
        skipped+=int(result.rowcount==0)
    db.execute("INSERT INTO operational_note_migrations_478 VALUES('sidecar_v1',?,?)",(imported,skipped))
    app.state.context.audit.log('legacy_notes_imported_478','workspace','legacy-sidecar','',{'imported':imported,'skipped':skipped,'original_retained':True})


@contextmanager
def notes_db(app):
    db=app.state.context.db
    with db.transaction(immediate=True):
        db.execute('''CREATE TABLE IF NOT EXISTS operational_findings_478(
            finding_id TEXT PRIMARY KEY,case_id TEXT NOT NULL,document_id TEXT NOT NULL,
            anchor_id TEXT NOT NULL,title TEXT NOT NULL,interpretation TEXT NOT NULL,
            source_excerpt TEXT NOT NULL,document_sha256 TEXT NOT NULL,source_url TEXT NOT NULL,
            created_by TEXT NOT NULL,created_at TEXT NOT NULL,review_state TEXT NOT NULL DEFAULT 'unreviewed',
            review_reason TEXT NOT NULL DEFAULT '',reviewed_by TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL DEFAULT 'research_note',anchor_hash TEXT NOT NULL DEFAULT '',
            legacy_imported INTEGER NOT NULL DEFAULT 0,record_hash TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS notes_478_case_idx ON operational_findings_478(case_id,created_at)')
        db.execute('CREATE TABLE IF NOT EXISTS operational_note_migrations_478(migration TEXT PRIMARY KEY,imported INTEGER,skipped INTEGER)')
        _import_old_notes(app,db)
        yield db


def checked_note(row):
    row=dict(row)
    if finding_hash(row)!=row['record_hash']:raise HTTPException(409,'Integrität des Arbeitsbefunds verletzt.')
    return row


def notes_for_case(app,case_id,*,offset=0,limit=None):
    with notes_db(app) as db:
        if limit is None:
            total=db.one('SELECT COUNT(*) AS n FROM operational_findings_478 WHERE case_id=?',(case_id,))['n']
            if total>10000:raise HTTPException(409,'Zu viele Befunde für einen vollständigen Einzelbericht.')
            rows=db.all('SELECT * FROM operational_findings_478 WHERE case_id=? ORDER BY rowid DESC',(case_id,))
        else:
            if type(offset) is not int or not 0<=offset<=100000 or limit!=50:raise HTTPException(422,'Ungültige Seite.')
            rows=db.all('SELECT * FROM operational_findings_478 WHERE case_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?',(case_id,limit,offset))
        return [checked_note(row) for row in rows]


async def bounded_form(request,max_bytes=40000):
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>max_bytes:raise HTTPException(413,'Formular zu groß.')
        data.extend(chunk)
    async def receive():return {'type':'http.request','body':bytes(data),'more_body':False}
    form=await Request(request.scope,receive=receive).form(max_fields=10,max_files=0,max_part_size=12000)
    if len(form.multi_items())>10:raise HTTPException(413,'Zu viele Formularfelder.')
    return form


def verify_post(app,request,user,submitted):
    csrf=request.cookies.get(CSRF_COOKIE,'')
    if not csrf or not hmac.compare_digest(csrf,str(submitted or '')) or not app.state.context.team_identity_359.csrf_token_valid(user,csrf):
        raise HTTPException(403,'Ungültiger Formularschutz. Bitte erneut anmelden.')
    if request.headers.get('sec-fetch-site','').lower() not in ('','same-origin','none'):
        raise HTTPException(403,'Fremder Formularursprung.')
    origin=request.headers.get('origin','')
    if origin:
        try:parsed=urlsplit(origin)
        except ValueError:raise HTTPException(403,'Fremder Formularursprung.') from None
        if parsed.scheme not in ('http','https') or parsed.netloc!=request.headers.get('host'):
            raise HTTPException(403,'Fremder Formularursprung.')


def get_anchor(ctx,user,case_id,document_id,anchor_id):
    service=ctx.document_intelligence_458
    service._identity(user,case_id,'case.read',document_id)
    try:doc=service._document(document_id);anchor=service._anchor(anchor_id)
    except KeyError:raise HTTPException(422,'Fundstelle nicht vorhanden.') from None
    if doc['case_id']!=case_id or anchor['case_id']!=case_id or anchor['document_id']!=document_id:
        raise HTTPException(403,'Fundstelle gehört nicht zu diesem Fall und Dokument.')
    if doc['state']=='extraction_rejected' or doc['record_hash']!=service._rh(doc) or anchor['record_hash']!=service._rh(anchor):
        raise HTTPException(409,'Quellenintegrität oder Extraktionsstatus verhindert die Übernahme.')
    if anchor['document_sha256']!=doc['document_sha256'] or not service._payload_current(doc):
        raise HTTPException(409,'Originalbeleg wurde verändert.')
    return doc,doc,anchor


def attach_findings(app,build):
    ctx=app.state.context
    with notes_db(app):pass

    @app.get('/workbench/findings',response_class=HTMLResponse)
    def findings_view(request:Request,case_id:str='',document_id:str='',anchor_offset:int=Query(0,ge=0,le=100000),offset:int=Query(0,ge=0,le=100000)):
        user,case=case_access(app,request,case_id)
        docs=ctx.document_intelligence_458.documents(identity=user,case_id=case_id)
        if document_id and all(d['document_id']!=document_id for d in docs):raise HTTPException(403,'Fremdes Dokument.')
        selected=next((d for d in docs if d['document_id']==document_id),docs[0] if docs else None)
        document_id=selected['document_id'] if selected else ''
        options=''.join('<option value="'+escape(d['document_id'],quote=True)+'"'+(' selected' if d['document_id']==document_id else '')+'>'+escape(d['title'][:160])+'</option>' for d in docs)
        picker='<form method="get"><input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'"><label>Dokument auswählen<select name="document_id">'+options+'</select></label><button>Fundstellen laden</button></form>'
        packet=ctx.document_intelligence_458.anchors(identity=user,document_id=document_id) if selected else {'anchors':[]}
        anchors=packet['anchors'];choices=[]
        for anchor in anchors[anchor_offset:anchor_offset+50]:
            ref=document_id+'|'+anchor['anchor_id'];label='Seite '+str(anchor['page_number'])+' · '+anchor['text_excerpt'][:160]
            choices.append('<option value="'+escape(ref,quote=True)+'">'+escape(label)+'</option>')
        pages=''
        for value,label in ((max(0,anchor_offset-50),'Frühere Fundstellen'),(anchor_offset+50,'Weitere Fundstellen')):
            if (label.startswith('Frühere') and anchor_offset>0) or (label.startswith('Weitere') and value<len(anchors)):
                pages+='<a href="'+escape('/workbench/findings?'+urlencode({'case_id':case_id,'document_id':document_id,'anchor_offset':value}),quote=True)+'">'+label+'</a> '
        token=escape(request.cookies.get(CSRF_COOKIE,''),quote=True)
        form='<section class="card"><h2>Neuen Arbeitsbefund speichern</h2>'+picker+'<p>'+str(len(anchors))+' Fundstellen · bis zu 50 je Seite.</p>'+pages
        form+='<form method="post"><input type="hidden" name="case_id" value="'+escape(case_id,quote=True)+'"><input type="hidden" name="csrf" value="'+token+'">'
        form+='<label>Originalfundstelle<select name="anchor_ref" required>'+(''.join(choices) or '<option value="">Zuerst ein lesbares Dokument importieren</option>')+'</select></label>'
        form+='<label>Einordnung<select name="kind">'+''.join('<option value="'+k+'">'+v+'</option>' for k,v in KINDS.items())+'</select></label>'
        form+='<label>Kurzbezeichnung<input name="title" required minlength="4" maxlength="180"></label><label>Eigene Beobachtung, Unsicherheit oder Gegenbeleg<textarea name="interpretation" required minlength="10" maxlength="2400" rows="5"></textarea></label><button>Mit Quelle als Arbeitsbefund speichern</button></form></section>'
        if 'research.run' not in ctx.team_governance_359.effective_capabilities(user,case_id):
            form='<p>Du kannst die Arbeitsbefunde lesen. Zum Anlegen ist eine Rechercheberechtigung in diesem Fall erforderlich.</p>'
        rows=notes_for_case(app,case_id,offset=offset,limit=50)
        items=''.join('<article class="card"><h2>'+escape(row['title'])+'</h2><p>'+escape(KINDS.get(row['kind'],'Arbeitsnotiz'))+' · '+escape(row['interpretation'])+'</p><blockquote>'+escape(row['source_excerpt'])+'</blockquote><a href="'+escape('/documents458?'+urlencode({'case_id':case_id,'document_id':row['document_id'],'anchor_id':row['anchor_id']})+'#anchor-'+row['anchor_id'],quote=True)+'">Originalfundstelle öffnen</a><p>Status: '+escape(row['review_state'])+' · '+escape(row['created_by'])+'</p></article>' for row in rows)
        nav=''
        for value,label in ((max(0,offset-50),'Neuere Arbeitsbefunde'),(offset+50,'Ältere Arbeitsbefunde')):
            if (offset>0 and value<offset) or (len(rows)==50 and value>offset):nav+='<a href="'+escape('/workbench/findings?'+urlencode({'case_id':case_id,'offset':value,'document_id':document_id}),quote=True)+'">'+label+'</a> '
        with notes_db(app) as db:migration=db.one("SELECT * FROM operational_note_migrations_478 WHERE migration='sidecar_v1'")
        notice='<p>Ältere Arbeitsnotizen übernommen und zur erneuten Prüfung markiert; Ursprungsdatei bleibt erhalten.</p>' if migration else ''
        if migration and migration['skipped']:notice+='<p>Einige ältere Notizen konnten nicht zugeordnet werden; Ursprungsdatei separat prüfen.</p>'
        return HTMLResponse(page('Quellengebundene Arbeitsbefunde',case_id,notice+form+items+'<p>'+nav+'</p>',build),headers={'Cache-Control':'no-store'})

    @app.post('/workbench/findings')
    async def add_finding(request:Request):
        form=await bounded_form(request);case_id=str(form.get('case_id',''))
        user,_=case_access(app,request,case_id,'research.run');verify_post(app,request,user,form.get('csrf',''))
        doc_id,separator,anchor_id=str(form.get('anchor_ref','')).partition('|')
        if not separator:raise HTTPException(422,'Bitte eine Originalfundstelle auswählen.')
        title=str(form.get('title','')).strip();interpretation=str(form.get('interpretation','')).strip();kind=str(form.get('kind','research_note'))
        if not 4<=len(title)<=180 or not 10<=len(interpretation)<=2400 or kind not in KINDS:raise HTTPException(422,'Titel, Einordnung oder Interpretation prüfen.')
        doc,_,anchor=get_anchor(ctx,user,case_id,doc_id,anchor_id)
        if not anchor['text_excerpt'].strip():raise HTTPException(422,'Originaltext fehlt.')
        row=dict(finding_id=secrets.token_hex(16),case_id=case_id,document_id=doc_id,anchor_id=anchor_id,
            title=title,interpretation=interpretation,source_excerpt=anchor['text_excerpt'],document_sha256=doc['document_sha256'],
            source_url=doc['source_url'],created_by=user['username'],created_at=datetime.now(timezone.utc).isoformat(),
            review_state='unreviewed',review_reason='',reviewed_by='',kind=kind,anchor_hash=anchor['record_hash'],legacy_imported=0)
        row['record_hash']=finding_hash(row);columns=BASE_COLUMNS+('record_hash',)
        with notes_db(app) as db:
            ctx.document_intelligence_458._identity(user,case_id,'research.run',case_id)
            current,_,current_anchor=get_anchor(ctx,user,case_id,doc_id,anchor_id)
            if current!=doc or current_anchor!=anchor:raise HTTPException(409,'Quellenstand wurde während der Übernahme verändert.')
            db.execute(INSERT_FINDING_SQL,tuple(row[k] for k in columns))
            ctx.audit.log('human_finding_created_478','finding',row['finding_id'],case_id,
                {'actor':user['username'],'document_id':doc_id,'anchor_hash':row['anchor_hash'],'claims_created':0})
        return RedirectResponse('/workbench/findings?'+urlencode({'case_id':case_id,'document_id':doc_id}),status_code=303)
